"""
Ad-hoc "test run" execution for the editor's Run button.

This is the shallow path — it runs whatever the user typed and hands back
stdout/stderr. The benchmark path (benchmarks.py) is the one that measures
scaling. Both go through sandbox.run_sandboxed; neither ever executes a
submission in the backend process.
"""

import re

from sandbox import (
    LANGUAGE_LIMITS,
    cpp_compile_and_run,
    java_compile_and_run,
    run_sandboxed,
)

CPP_SCAFFOLD = """\
#include <iostream>
#include <vector>
#include <algorithm>
#include <unordered_map>
#include <string>
using namespace std;

{code}

int main() {{
    cout << "OK - function defined, use battle mode to benchmark" << endl;
    return 0;
}}
"""

JAVA_SCAFFOLD = """\
public class Solution {{
    {code}

    public static void main(String[] args) {{
        System.out.println("OK - function defined, use battle mode to benchmark");
    }}
}}
"""


def _result(res, language: str) -> dict:
    limits = LANGUAGE_LIMITS[language]
    stderr = res.stderr
    if res.timed_out:
        stderr = f"Timed out after {limits.wall_clock_s:g}s.\n{stderr}".strip()
    elif res.oom_killed:
        stderr = f"Killed: exceeded the {limits.memory_mb} MB memory limit.\n{stderr}".strip()

    return {
        "stdout": res.stdout,
        "stderr": stderr,
        "time_ms": res.duration_ms,
        "compile_error": res.compile_failed,
        "timed_out": res.timed_out,
        "oom_killed": res.oom_killed,
        # The UI shows the ceiling the submission ran under rather than a
        # memory reading. Peak RSS was previously sampled after the process
        # had already exited, which reported a meaningless number.
        "memory_limit_mb": limits.memory_mb,
        "time_limit_s": limits.wall_clock_s,
        "isolated": res.isolated,
    }


def run_python(code: str) -> dict:
    res = run_sandboxed("python", {"solution.py": code}, ["solution.py"])
    return _result(res, "python")


def run_cpp(code: str) -> dict:
    source = code if "int main(" in code else CPP_SCAFFOLD.format(code=code)
    res = run_sandboxed("cpp", {"solution.cpp": source}, cpp_compile_and_run())
    return _result(res, "cpp")


def run_java(code: str) -> dict:
    if "public class" in code:
        source = code
        match = re.search(r"public\s+class\s+(\w+)", code)
        class_name = match.group(1) if match else "Solution"
    else:
        source = JAVA_SCAFFOLD.format(code=code)
        class_name = "Solution"

    res = run_sandboxed(
        "java",
        {f"{class_name}.java": source},
        java_compile_and_run(class_name),
    )
    return _result(res, "java")


RUNNERS = {"python": run_python, "cpp": run_cpp, "java": run_java}


def run_submission(code: str, language: str = "python") -> dict:
    return RUNNERS.get(language, run_python)(code)
