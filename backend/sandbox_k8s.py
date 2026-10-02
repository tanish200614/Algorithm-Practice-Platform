"""
Kubernetes execution backend.

The Docker backend starts containers through /var/run/docker.sock, which is
basically root on the host. Fine on a laptop, not great in a cluster. Here
each submission runs as a Job created through the API instead, so no pod ever
touches a container runtime socket.

How the Docker settings map over:

    --network none              NetworkPolicy denying all egress
    --memory / --cpus           resources.limits
    --user 10001                securityContext.runAsUser
    --cap-drop ALL              capabilities.drop: [ALL]
    --security-opt no-new-priv  allowPrivilegeEscalation: false
    host-side timeout kill      activeDeadlineSeconds

The runner pod also mounts no service account token, so even if code reaches
the network there's no API it can call.
"""

import json
import os
import subprocess
import time
import uuid

NAMESPACE = os.environ.get("SANDBOX_NAMESPACE", "algobattle")

# Label everything we create so leftovers from a crashed backend can be found
# and cleaned up without touching anything else in the namespace.
RUNNER_LABEL = "algobattle.io/runner"

_KUBECTL_TIMEOUT_S = 30


def _kubectl(*args, stdin: str = None, timeout: int = _KUBECTL_TIMEOUT_S):
    return subprocess.run(
        ["kubectl", "-n", NAMESPACE, *args],
        input=stdin, capture_output=True, text=True, timeout=timeout,
    )


def kubectl_available() -> bool:
    """Whether a cluster is reachable and the namespace exists."""
    try:
        if subprocess.run(["kubectl", "version", "--client"],
                          capture_output=True, timeout=10).returncode != 0:
            return False
        return _kubectl("get", "namespace", NAMESPACE, timeout=10).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _job_manifest(name: str, image: str, command: list, limits, files: dict) -> str:
    """
    Build the Job. Files are mounted from a ConfigMap at /work instead of
    going in the command, so quotes or shell characters in a submission can't
    break out.
    """
    container = {
        "name": "runner",
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "args": command,
        "workingDir": "/work",
        "resources": {
            "limits": {
                "memory": f"{limits.memory_mb}Mi",
                "cpu": str(limits.cpus),
            },
            "requests": {
                "memory": f"{min(limits.memory_mb, 64)}Mi",
                "cpu": "100m",
            },
        },
        "securityContext": {
            "runAsUser": 10001,
            "runAsGroup": 10001,
            "runAsNonRoot": True,
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        "volumeMounts": [
            {"name": "work", "mountPath": "/work", "readOnly": True},
            # The root filesystem is read-only, so compilers and the JVM need
            # somewhere to write. In RAM, and counted against the pod's memory.
            {"name": "scratch", "mountPath": "/tmp"},
        ],
    }

    manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "labels": {RUNNER_LABEL: "true"}},
        "spec": {
            "backoffLimit": 0,          # a failed submission is a result, not a retry
            "completions": 1,
            "parallelism": 1,
            "activeDeadlineSeconds": int(limits.wall_clock_s),
            "ttlSecondsAfterFinished": 300,   # backstop if explicit cleanup is missed
            "template": {
                "metadata": {"labels": {RUNNER_LABEL: "true"}},
                "spec": {
                    "restartPolicy": "Never",
                    # Don't give untrusted code credentials for the API running it.
                    "automountServiceAccountToken": False,
                    "enableServiceLinks": False,
                    "containers": [container],
                    "volumes": [
                        {"name": "work", "configMap": {"name": name}},
                        {"name": "scratch", "emptyDir": {
                            "medium": "Memory",
                            "sizeLimit": "64Mi",
                        }},
                    ],
                },
            },
        },
    }
    return json.dumps(manifest)


def _configmap_manifest(name: str, files: dict) -> str:
    return json.dumps({
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "labels": {RUNNER_LABEL: "true"}},
        "data": files,
    })


def _pod_state(name: str) -> dict:
    """Terminated-container state for the job's pod, or {} if not there yet."""
    res = _kubectl("get", "pod", "-l", f"job-name={name}",
                   "-o", "jsonpath={.items[0].status.containerStatuses[0].state.terminated}")
    if res.returncode != 0 or not res.stdout.strip():
        return {}
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {}


def _job_failed_deadline(name: str) -> bool:
    res = _kubectl("get", "job", name,
                   "-o", "jsonpath={.status.conditions[?(@.type=='Failed')].reason}")
    return "DeadlineExceeded" in (res.stdout or "")


def _cleanup(name: str):
    # Best effort: ttlSecondsAfterFinished and the label sweep both cover a miss.
    _kubectl("delete", "job", name, "--ignore-not-found", "--wait=false")
    _kubectl("delete", "configmap", name, "--ignore-not-found", "--wait=false")


def run_k8s_job(image: str, files: dict, command: list, limits, result_cls):
    """Run one submission as a Job. Returns a SandboxResult."""
    name = f"run-{uuid.uuid4().hex[:16]}"
    started = time.monotonic()

    try:
        cm = _kubectl("apply", "-f", "-", stdin=_configmap_manifest(name, files))
        if cm.returncode != 0:
            return result_cls("", f"Could not stage submission: {cm.stderr[:200]}",
                              -1, 0.0, isolated=True)

        job = _kubectl("apply", "-f", "-",
                       stdin=_job_manifest(name, image, command, limits, files))
        if job.returncode != 0:
            return result_cls("", f"Could not schedule run: {job.stderr[:200]}",
                              -1, 0.0, isolated=True)

        # activeDeadlineSeconds bounds the pod; this bounds the wait on top of
        # it, so a cluster that never schedules the pod cannot hang a request.
        deadline = limits.wall_clock_s + 30
        wait = _kubectl(
            "wait", f"job/{name}",
            "--for=condition=complete", f"--timeout={int(deadline)}s",
            timeout=int(deadline) + 10,
        )
        completed = wait.returncode == 0
        if not completed:
            _kubectl("wait", f"job/{name}", "--for=condition=failed", "--timeout=5s")

        duration_ms = round((time.monotonic() - started) * 1000, 2)

        logs = _kubectl("logs", f"job/{name}", "--tail=-1")
        stdout = logs.stdout if logs.returncode == 0 else ""

        if _job_failed_deadline(name):
            return result_cls(stdout[:limits.output_bytes], "", 124, duration_ms,
                              timed_out=True, isolated=True)

        state = _pod_state(name)
        exit_code = state.get("exitCode", 0 if completed else -1)
        oom = state.get("reason") == "OOMKilled"

        return result_cls(
            stdout[: limits.output_bytes],
            "" if exit_code == 0 else (state.get("message") or stdout)[:2000],
            exit_code,
            duration_ms,
            oom_killed=oom,
            isolated=True,
        )
    finally:
        _cleanup(name)
