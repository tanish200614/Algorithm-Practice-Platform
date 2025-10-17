import subprocess, tempfile, time, os, sys, re
import psutil


def run_python(code: str):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    start = time.time()
    proc = psutil.Popen([sys.executable, path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate(timeout=10)
    duration = round((time.time() - start) * 1000, 2)
    try:
        mem = proc.memory_info().rss // 1024
    except Exception:
        mem = 0
    return stdout.decode(), stderr.decode(), duration, mem


def run_cpp(code: str):
    tmpdir = tempfile.mkdtemp()
    src = os.path.join(tmpdir, "solution.cpp")
    binary = os.path.join(tmpdir, "solution")

    if "int main(" not in code:
        full_code = f"""
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
    else:
        full_code = code

    with open(src, "w") as f:
        f.write(full_code)
    compile_proc = subprocess.run(
        ["g++", "-O2", "-std=c++17", "-o", binary, src],
        capture_output=True, text=True, timeout=15
    )
    if compile_proc.returncode != 0:
        return "", compile_proc.stderr, 0, 0
    start = time.time()
    proc = psutil.Popen([binary], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate(timeout=10)
    duration = round((time.time() - start) * 1000, 2)
    try:
        mem = proc.memory_info().rss // 1024
    except Exception:
        mem = 0
    return stdout.decode(), stderr.decode(), duration, mem


def run_java(code: str):
    tmpdir = tempfile.mkdtemp()

    if "public class" not in code:
        full_code = f"""
public class Solution {{
    {code}

    public static void main(String[] args) {{
        System.out.println("OK - function defined, use battle mode to benchmark");
    }}
}}
"""
        classname = "Solution"
    else:
        full_code = code
        match = re.search(r'public\s+class\s+(\w+)', code)
        classname = match.group(1) if match else "Solution"

    src = os.path.join(tmpdir, f"{classname}.java")
    with open(src, "w") as f:
        f.write(full_code)
    compile_proc = subprocess.run(
        ["javac", src],
        capture_output=True, text=True, timeout=15
    )
    if compile_proc.returncode != 0:
        return "", compile_proc.stderr, 0, 0
    start = time.time()
    proc = psutil.Popen(
        ["java", "-cp", tmpdir, classname],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = proc.communicate(timeout=10)
    duration = round((time.time() - start) * 1000, 2)
    try:
        mem = proc.memory_info().rss // 1024
    except Exception:
        mem = 0
    return stdout.decode(), stderr.decode(), duration, mem
