"""
Sandbox tests.

The isolation checks (no network, non-root uid, memory limit) need real
containers, so they skip if the images aren't built. Everything else runs
anywhere.
"""

import dataclasses

import pytest

import sandbox
from sandbox import DEFAULT_LIMITS, run_sandboxed

requires_docker = pytest.mark.skipif(
    not sandbox.docker_available("python"),
    reason="python sandbox image not built; run sandbox/build.sh",
)


class TestProbeCache:
    def test_unprobed_cache_is_not_mistaken_for_a_result(self, monkeypatch):
        """time.monotonic() can start near zero, so a 0.0 sentinel would look
        like a fresh 'unavailable' result and skip the Docker check for the
        first 30 seconds."""
        calls = []

        def fake_probe():
            calls.append(1)
            return "stub", {"python"}

        monkeypatch.setattr(sandbox, "_probe_cache", None)
        monkeypatch.setattr(sandbox, "_probe_docker", fake_probe)
        monkeypatch.setattr(sandbox.time, "monotonic", lambda: 0.01)

        assert sandbox.docker_available("python") is True
        assert len(calls) == 1

    def test_result_is_cached_within_the_ttl(self, monkeypatch):
        calls = []
        monkeypatch.setattr(sandbox, "_probe_cache", None)
        monkeypatch.setattr(
            sandbox, "_probe_docker", lambda: (calls.append(1), ("stub", {"python"}))[1]
        )
        monkeypatch.setattr(sandbox.time, "monotonic", lambda: 100.0)

        sandbox.docker_available()
        sandbox.docker_available()
        assert len(calls) == 1


    def test_one_missing_image_does_not_disarm_the_others(self, monkeypatch):
        """A partially built image set used to drop every language to host
        execution, including the ones whose image was present."""
        monkeypatch.setattr(sandbox, "_probe_cache", None)
        monkeypatch.setattr(sandbox, "_probe_docker", lambda: ("stub", {"python", "cpp"}))
        monkeypatch.setattr(sandbox.time, "monotonic", lambda: 100.0)

        assert sandbox.docker_available("python") is True
        assert sandbox.docker_available("cpp") is True
        assert sandbox.docker_available("java") is False

        status = sandbox.sandbox_status()
        assert status["mode"] == "partial"
        # Not every language is isolated, so this must not read as safe.
        assert status["isolated"] is False
        assert status["languages"] == {"python": True, "cpp": True, "java": False}


class TestExecution:
    def test_runs_python_and_captures_stdout(self):
        res = run_sandboxed("python", {"h.py": "print(6 * 7)"}, ["h.py"])
        assert res.stdout.strip() == "42"
        assert res.ok

    def test_reports_a_traceback_without_crashing(self):
        res = run_sandboxed("python", {"h.py": "raise ValueError('boom')"}, ["h.py"])
        assert not res.ok
        assert "boom" in res.stderr

    def test_wall_clock_limit_kills_a_spinning_submission(self):
        """A busy loop burns CPU as fast as wall time. Without headroom on the
        CPU rlimit both limits fire together, and on Linux this showed up as
        an unexplained kill instead of a timeout."""
        limits = dataclasses.replace(DEFAULT_LIMITS, wall_clock_s=3.0)
        res = run_sandboxed("python", {"h.py": "while True: pass"}, ["h.py"], limits=limits)
        assert res.timed_out
        assert res.exit_code == 124

    def test_a_sleeping_submission_also_times_out(self):
        """Sleeping uses no CPU, so only the wall clock can catch this. Shows
        the timeout doesn't depend on the CPU rlimit."""
        limits = dataclasses.replace(DEFAULT_LIMITS, wall_clock_s=3.0)
        res = run_sandboxed(
            "python", {"h.py": "import time; time.sleep(60)"}, ["h.py"], limits=limits
        )
        assert res.timed_out
        assert res.exit_code == 124

    def test_unknown_language_is_rejected(self):
        assert run_sandboxed("brainfuck", {}, []).exit_code == -1

    def test_compile_failure_is_distinct_from_a_runtime_failure(self):
        res = run_sandboxed(
            "cpp",
            {"solution.cpp": "int main() { this is not valid c++ }"},
            sandbox.cpp_compile_and_run(),
        )
        assert res.compile_failed
        assert "error" in res.stderr.lower()

    def test_a_compiling_program_is_not_flagged_as_a_compile_error(self):
        res = run_sandboxed(
            "cpp",
            {"solution.cpp": "#include <cstdlib>\nint main() { return 3; }"},
            sandbox.cpp_compile_and_run(),
        )
        assert not res.compile_failed
        assert res.exit_code == 3


@requires_docker
class TestIsolation:
    """The core isolation guarantees."""

    def test_submissions_cannot_reach_the_network(self):
        code = (
            "import socket\n"
            "socket.setdefaulttimeout(3)\n"
            "try:\n"
            "    socket.create_connection(('1.1.1.1', 53))\n"
            "    print('REACHABLE')\n"
            "except OSError:\n"
            "    print('blocked')\n"
        )
        res = run_sandboxed("python", {"h.py": code}, ["h.py"])
        assert res.stdout.strip() == "blocked"

    def test_submissions_do_not_run_as_root(self):
        res = run_sandboxed("python", {"h.py": "import os; print(os.getuid())"}, ["h.py"])
        assert res.stdout.strip() == str(sandbox.SANDBOX_UID)

    def test_exceeding_the_memory_limit_is_killed(self):
        limits = dataclasses.replace(DEFAULT_LIMITS, memory_mb=128)
        code = "x = bytearray(400 * 1024 * 1024)\nprint('allocated')"
        res = run_sandboxed("python", {"h.py": code}, ["h.py"], limits=limits)
        assert res.oom_killed
        assert "allocated" not in res.stdout

    def test_a_fork_bomb_is_contained(self):
        limits = dataclasses.replace(DEFAULT_LIMITS, pids=32, wall_clock_s=10.0)
        res = run_sandboxed(
            "python", {"h.py": "import os\nwhile True: os.fork()"}, ["h.py"], limits=limits
        )
        assert not res.ok

    def test_the_host_filesystem_is_not_visible(self):
        code = "import os; print(os.path.exists('/app/main.py'), os.path.exists('/etc/shadow'))"
        res = run_sandboxed("python", {"h.py": code}, ["h.py"])
        assert res.stdout.strip().startswith("False")
