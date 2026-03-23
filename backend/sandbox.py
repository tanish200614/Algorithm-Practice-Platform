"""
Isolation layer for untrusted code.

Every submission the platform runs — ad-hoc test runs, benchmark harnesses,
assembly dumps — goes through `run_sandboxed`. The primary path puts the code
in a throwaway per-language container with no network, dropped capabilities,
an unprivileged uid, and hard CPU / memory / process / wall-clock ceilings.

If the Docker daemon or the sandbox images are unavailable (a laptop with
Docker Desktop closed, say) it degrades to running on the host under POSIX
rlimits. That fallback is *weaker* — it constrains resources but does not
isolate the filesystem or the network — so it is meant for local development
only, and `sandbox_status()` reports which mode is live.
"""

import os
import platform
import resource
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, replace

# Exit code the C++/Java wrapper scripts use to signal "compilation failed"
# rather than "the program itself failed".
COMPILE_ERROR_EXIT = 91

# Must match the uid the sandbox images create. Deliberately high: the
# eclipse-temurin base already owns 1000.
SANDBOX_UID = 10001

SANDBOX_TAG = os.environ.get("SANDBOX_TAG", "latest")

IMAGES = {
    "python": f"algobattle-sandbox-python:{SANDBOX_TAG}",
    "cpp": f"algobattle-sandbox-cpp:{SANDBOX_TAG}",
    "java": f"algobattle-sandbox-java:{SANDBOX_TAG}",
}

# Set SANDBOX_MODE=docker to refuse to fall back — the right setting in any
# deployed environment, where silently running untrusted code on the host
# would be much worse than failing the request.
SANDBOX_MODE = os.environ.get("SANDBOX_MODE", "auto").lower()


@dataclass(frozen=True)
class Limits:
    cpus: float = 1.0           # fraction of one core
    memory_mb: int = 256
    pids: int = 64              # caps fork bombs
    wall_clock_s: float = 15.0
    output_bytes: int = 256 * 1024


DEFAULT_LIMITS = Limits()

# The JVM wants far more address space and threads than a Python process, and
# compilers are slower to start than the programs they produce.
LANGUAGE_LIMITS = {
    "python": DEFAULT_LIMITS,
    "cpp": replace(DEFAULT_LIMITS, memory_mb=512, wall_clock_s=25.0),
    "java": replace(DEFAULT_LIMITS, memory_mb=768, pids=256, wall_clock_s=30.0),
}


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timed_out: bool = False
    oom_killed: bool = False
    isolated: bool = True       # False when the host fallback ran it

    @property
    def compile_failed(self) -> bool:
        return self.exit_code == COMPILE_ERROR_EXIT

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


# ── Docker availability (cached, but re-checked so a later `docker start`
#    is picked up without restarting the backend) ────────────────────────────

# None means "never probed". A 0.0 timestamp would not work as the sentinel:
# time.monotonic() can start near zero, so a fresh process would read the
# sentinel as a still-valid "unavailable" result and quietly take the host
# fallback without ever asking the daemon.
_probe_cache = None
_PROBE_TTL_S = 30.0


def _probe_docker() -> tuple:
    if not shutil.which("docker"):
        return False, "docker CLI not found on PATH"
    try:
        info = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"docker info failed: {e}"
    if info.returncode != 0:
        return False, "Docker daemon is not running"

    missing = []
    for lang, image in IMAGES.items():
        probe = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True, text=True, timeout=15,
        )
        if probe.returncode != 0:
            missing.append(image)
    if missing:
        return False, f"sandbox images not built: {', '.join(missing)} (run sandbox/build.sh)"
    return True, f"docker {info.stdout.strip()}"


def docker_available() -> bool:
    global _probe_cache
    if _probe_cache is not None:
        checked_at, available, _ = _probe_cache
        if time.monotonic() - checked_at < _PROBE_TTL_S:
            return available
    available, detail = _probe_docker()
    _probe_cache = (time.monotonic(), available, detail)
    return available


def _probe_detail() -> str:
    return _probe_cache[2] if _probe_cache else ""


def sandbox_status() -> dict:
    available = docker_available()
    detail = _probe_detail()
    if available:
        mode = "docker"
    elif SANDBOX_MODE == "docker":
        mode = "unavailable"
    else:
        mode = "host-rlimit"
    caveats = []
    if mode == "host-rlimit":
        caveats.append("no filesystem or network isolation — development only")
        if _IS_DARWIN:
            caveats.append("memory is not capped on macOS (RLIMIT_AS is unusable here)")
    return {
        "mode": mode,
        "isolated": mode == "docker",
        "detail": detail,
        "caveats": caveats,
        "images": IMAGES if mode == "docker" else {},
    }


# ── Docker execution ──────────────────────────────────────────────────────────

def _docker_create_argv(image: str, limits: Limits, name: str, command: list) -> list:
    return [
        "docker", "create",
        "--name", name,
        # No route to anything: no exfiltration, no fetching a payload, no
        # hammering someone else's host from our IP.
        "--network", "none",
        # A submission that allocates without bound is killed rather than
        # taking the machine down. memory-swap == memory disables swap, so the
        # limit is real instead of just slow.
        "--memory", f"{limits.memory_mb}m",
        "--memory-swap", f"{limits.memory_mb}m",
        "--cpus", str(limits.cpus),
        # Fork bombs hit this before they hit the scheduler.
        "--pids-limit", str(limits.pids),
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", f"{SANDBOX_UID}:{SANDBOX_UID}",
        "--workdir", "/work",
        # Compilers and the JVM need scratch space; keep it small and in RAM.
        "--tmpfs", "/tmp:rw,size=64m,mode=1777,exec",
        image,
        *command,
    ]


def _run_docker(language: str, files: dict, command: list, limits: Limits) -> SandboxResult:
    image = IMAGES[language]
    name = f"algobattle-{uuid.uuid4().hex[:12]}"
    workdir = tempfile.mkdtemp(prefix="algobattle-")
    started = time.monotonic()

    try:
        for filename, content in files.items():
            with open(os.path.join(workdir, filename), "w") as f:
                f.write(content)

        created = subprocess.run(
            _docker_create_argv(image, limits, name, command),
            capture_output=True, text=True, timeout=30,
        )
        if created.returncode != 0:
            return SandboxResult(
                stdout="", stderr=f"sandbox create failed: {created.stderr.strip()[:400]}",
                exit_code=-1, duration_ms=0.0,
            )

        copied = subprocess.run(
            ["docker", "cp", f"{workdir}/.", f"{name}:/work"],
            capture_output=True, text=True, timeout=30,
        )
        if copied.returncode != 0:
            return SandboxResult(
                stdout="", stderr=f"sandbox copy failed: {copied.stderr.strip()[:400]}",
                exit_code=-1, duration_ms=0.0,
            )

        timed_out = False
        started = time.monotonic()
        try:
            proc = subprocess.run(
                ["docker", "start", "--attach", name],
                capture_output=True, text=True, timeout=limits.wall_clock_s,
            )
            stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            # `docker start` giving up does not stop the container — kill it,
            # or the submission keeps burning its CPU share indefinitely.
            timed_out = True
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=15)
            stdout = _as_text(e.stdout)
            stderr = _as_text(e.stderr) or f"Wall-clock limit of {limits.wall_clock_s:g}s exceeded"
            exit_code = 124

        duration_ms = round((time.monotonic() - started) * 1000, 2)
        oom = (not timed_out) and exit_code == 137

        return SandboxResult(
            stdout=stdout[: limits.output_bytes],
            stderr=stderr[: limits.output_bytes],
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=timed_out,
            oom_killed=oom,
            isolated=True,
        )
    finally:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=20)
        shutil.rmtree(workdir, ignore_errors=True)


def _as_text(raw) -> str:
    if raw is None:
        return ""
    return raw.decode(errors="replace") if isinstance(raw, bytes) else raw


# ── Host fallback (development only) ─────────────────────────────────────────

_IS_DARWIN = platform.system() == "Darwin"


def _rlimit_preexec(limits: Limits, language: str):
    """Applied in the child between fork and exec."""
    def apply():
        cpu_s = max(1, int(limits.wall_clock_s))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (limits.output_bytes * 4, limits.output_bytes * 4)
        )

        # Address space. Two platforms have to be treated differently:
        #   - macOS counts the interpreter's own reserved mappings against
        #     RLIMIT_AS, so any limit small enough to be useful kills the child
        #     before it can exec. There is no working equivalent, which is one
        #     more reason the host path is development-only.
        #   - The JVM reserves a huge virtual range up front and refuses to
        #     start under RLIMIT_AS at all.
        if not _IS_DARWIN and language != "java":
            addr = limits.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (addr, addr))

        # macOS reports RLIMIT_NPROC per-user, so lowering it here would
        # throttle the developer's whole session rather than this child.
        if not _IS_DARWIN:
            resource.setrlimit(resource.RLIMIT_NPROC, (limits.pids, limits.pids))

        # New session, so a timeout can take the whole process group down
        # rather than leaving orphaned children spinning.
        os.setsid()
    return apply


def _run_host(language: str, files: dict, command: list, limits: Limits) -> SandboxResult:
    workdir = tempfile.mkdtemp(prefix="algobattle-host-")
    try:
        for filename, content in files.items():
            with open(os.path.join(workdir, filename), "w") as f:
                f.write(content)

        argv = _host_argv(language, command)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": workdir,
            "TMPDIR": workdir,
            "LANG": "C.UTF-8",
        }

        started = time.monotonic()
        timed_out = False
        proc = subprocess.Popen(
            argv, cwd=workdir, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=_rlimit_preexec(limits, language),
        )
        try:
            stdout, stderr = proc.communicate(timeout=limits.wall_clock_s)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            # The child called setsid(), so signal the whole group — killing
            # only the direct child would leave a compiler or a JVM it spawned
            # running.
            _kill_process_group(proc)
            stdout, stderr = proc.communicate()
            stderr = stderr or f"Wall-clock limit of {limits.wall_clock_s:g}s exceeded"
            exit_code = 124

        return SandboxResult(
            stdout=stdout[: limits.output_bytes],
            stderr=stderr[: limits.output_bytes],
            exit_code=exit_code,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
            timed_out=timed_out,
            isolated=False,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _kill_process_group(proc: subprocess.Popen):
    import signal
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


def _host_argv(language: str, command: list) -> list:
    """Reproduce each image's ENTRYPOINT for the no-Docker path."""
    if language == "python":
        import sys
        return [sys.executable, *command]
    # cpp and java images take a single shell string.
    return ["/bin/sh", "-c", command[0]]


# ── Entry point ───────────────────────────────────────────────────────────────

def run_sandboxed(language: str, files: dict, command: list,
                  limits: Limits = None) -> SandboxResult:
    """
    Run `command` against `files` (filename -> contents) in isolation.

    For Python, `command` is argv for the interpreter (e.g. ["harness.py"]).
    For C++ and Java it is a single-element list holding a shell command,
    matching those images' entrypoints.
    """
    if language not in IMAGES:
        return SandboxResult("", f"Unsupported language: {language}", -1, 0.0)

    limits = limits or LANGUAGE_LIMITS.get(language, DEFAULT_LIMITS)

    if docker_available():
        return _run_docker(language, files, command, limits)

    if SANDBOX_MODE == "docker":
        return SandboxResult(
            stdout="",
            stderr=f"Sandbox unavailable and SANDBOX_MODE=docker forbids the host "
                   f"fallback: {_probe_detail()}",
            exit_code=-1, duration_ms=0.0, isolated=False,
        )

    return _run_host(language, files, command, limits)


# ── Shell wrappers for the compiled languages ────────────────────────────────
#
# Compilation happens inside the sandbox, so a failed compile has to be
# distinguishable from a program that ran and failed. Both wrappers exit with
# COMPILE_ERROR_EXIT and put the compiler's message on stderr.

def cpp_compile_and_run(source_name: str = "solution.cpp", opt: str = "-O2",
                        std: str = "c++17") -> list:
    return [
        f'g++ {opt} -std={std} -o /tmp/solution {source_name} 2>/tmp/cc.err '
        f'|| {{ cat /tmp/cc.err >&2; exit {COMPILE_ERROR_EXIT}; }}; '
        f'exec /tmp/solution'
    ]


def cpp_compile_to_asm(source_name: str = "solution.cpp", opt: str = "-O2",
                       std: str = "c++17", intel: bool = True) -> list:
    syntax = "-masm=intel " if intel else ""
    return [
        f'g++ -S {opt} -std={std} -fverbose-asm {syntax}-o /tmp/solution.s {source_name} '
        f'2>/tmp/cc.err || {{ cat /tmp/cc.err >&2; exit {COMPILE_ERROR_EXIT}; }}; '
        f'cat /tmp/solution.s'
    ]


def java_compile_and_run(class_name: str = "Solution") -> list:
    return [
        f'javac -d /tmp {class_name}.java 2>/tmp/cc.err '
        f'|| {{ cat /tmp/cc.err >&2; exit {COMPILE_ERROR_EXIT}; }}; '
        f'exec java -XX:-UsePerfData -cp /tmp {class_name}'
    ]
