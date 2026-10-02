"""
Kubernetes execution backend.

These need a reachable cluster with the algobattle namespace and the Python
sandbox image loaded, so they skip everywhere else. The manifest builder is
pure and runs anywhere.
"""

import dataclasses
import json

import pytest

import sandbox_k8s
from sandbox import DEFAULT_LIMITS, SandboxResult
from sandbox_k8s import run_k8s_job

IMAGE = "algobattle-sandbox-python:latest"

requires_cluster = pytest.mark.skipif(
    not sandbox_k8s.kubectl_available(),
    reason="no reachable cluster/namespace (see deploy/k8s/README.md)",
)


def run(code, **limit_overrides):
    limits = dataclasses.replace(DEFAULT_LIMITS, **limit_overrides)
    return run_k8s_job(IMAGE, {"h.py": code}, ["h.py"], limits, SandboxResult)


class TestManifest:
    """Check the security fields directly so a bad edit to the manifest fails
    here instead of quietly loosening the sandbox."""

    def setup_method(self):
        raw = sandbox_k8s._job_manifest("j", IMAGE, ["h.py"], DEFAULT_LIMITS, {})
        self.job = json.loads(raw)
        self.pod = self.job["spec"]["template"]["spec"]
        self.container = self.pod["containers"][0]

    def test_the_runner_gets_no_api_credentials(self):
        """Untrusted code shouldn't get a token for the API running it. Docker
        has no equivalent for this."""
        assert self.pod["automountServiceAccountToken"] is False

    def test_the_container_is_unprivileged(self):
        sc = self.container["securityContext"]
        assert sc["runAsUser"] == 10001
        assert sc["runAsNonRoot"] is True
        assert sc["allowPrivilegeEscalation"] is False
        assert sc["readOnlyRootFilesystem"] is True
        assert sc["capabilities"]["drop"] == ["ALL"]

    def test_a_failed_submission_is_not_retried(self):
        """backoffLimit 0: a submission that fails is a result to report, not
        a transient error to run again."""
        assert self.job["spec"]["backoffLimit"] == 0

    def test_limits_are_carried_onto_the_pod(self):
        limits = dataclasses.replace(DEFAULT_LIMITS, memory_mb=333, wall_clock_s=7)
        job = json.loads(sandbox_k8s._job_manifest("j", IMAGE, [], limits, {}))
        assert job["spec"]["activeDeadlineSeconds"] == 7
        assert job["spec"]["template"]["spec"]["containers"][0][
            "resources"]["limits"]["memory"] == "333Mi"

    def test_the_runner_is_labelled_for_the_network_policy(self):
        """The NetworkPolicy selects on this label. Without it the egress ban
        silently stops applying."""
        assert self.pod_labels()[sandbox_k8s.RUNNER_LABEL] == "true"

    def pod_labels(self):
        return self.job["spec"]["template"]["metadata"]["labels"]


@requires_cluster
class TestExecution:
    def test_a_submission_runs_and_returns_output(self):
        res = run("print(6 * 7)")
        assert res.stdout.strip() == "42"
        assert res.ok
        assert res.isolated

    def test_submissions_do_not_run_as_root(self):
        assert run("import os; print(os.getuid())").stdout.strip() == "10001"

    def test_the_root_filesystem_is_read_only(self):
        code = ("try:\n"
                "    open('/etc/pwn','w').write('x'); print('WRITABLE')\n"
                "except OSError: print('read-only')\n")
        assert run(code).stdout.strip() == "read-only"

    def test_no_service_account_token_is_mounted(self):
        code = ("import os; print(os.path.exists("
                "'/var/run/secrets/kubernetes.io/serviceaccount/token'))")
        assert run(code).stdout.strip() == "False"

    def test_exceeding_the_memory_limit_is_killed(self):
        res = run("x = bytearray(400*1024*1024); print('allocated')", memory_mb=128)
        assert res.oom_killed
        assert "allocated" not in res.stdout

    def test_a_spinning_submission_hits_the_deadline(self):
        res = run("while True: pass", wall_clock_s=8)
        assert res.timed_out
        assert res.exit_code == 124

    def test_submissions_cannot_reach_the_network(self):
        """Requires a NetworkPolicy-enforcing CNI. kind's default kindnet
        accepts the policy and ignores it, which is why the cluster config
        disables it in favour of Calico."""
        code = ("import socket\n"
                "socket.setdefaulttimeout(5)\n"
                "try:\n"
                "    socket.create_connection(('1.1.1.1', 53)); print('REACHABLE')\n"
                "except OSError: print('blocked')\n")
        assert run(code).stdout.strip() == "blocked"
