import subprocess, tempfile, sys, os, json, math

from problems import PROBLEMS
from ml import clusterer as _clusterer, predict_next

INPUT_SIZES = [100, 500, 1000, 3000, 7000, 15000]


# ── Python harness ────────────────────────────────────────────────────────────

def make_python_harness(user_code, problem, n):
    # More repeats at small n so fast algorithms have measurable timing
    repeats = max(1, min(200, 20000 // n))
    return f"""
import time, json, sys, random

{problem['input_generator']}
{user_code}
{problem['validator']}

args = gen({n})
repeats = {repeats}
try:
    {problem['function_name']}(*args)  # warmup
    start = time.perf_counter()
    for _ in range(repeats):
        result = {problem['function_name']}(*args)
    elapsed = (time.perf_counter() - start) * 1000 / repeats
    ok = validate(result, *args)
    print(json.dumps({{"n": {n}, "ms": round(elapsed, 6), "ok": ok}}))
except Exception as e:
    print(json.dumps({{"n": {n}, "ms": None, "ok": False, "err": str(e)}}))
"""


# ── C++ harnesses ─────────────────────────────────────────────────────────────

CPP_HARNESSES = {
    "two_sum": """
#include <iostream>
#include <vector>
#include <chrono>
#include <algorithm>
#include <cstdlib>
using namespace std;
// USER_CODE
int main() {
    srand(42 + N_VAL);
    int n = N_VAL;
    vector<int> nums(n);
    for (int k = 0; k < n - 2; k++) nums[k] = rand() % 1999 - 999;
    nums[n-2] = 10001; nums[n-1] = 10002;
    int target = 20003;
    int repeats = max(1, min(2000, 200000 / n));
    two_sum(nums, target); // warmup
    auto start = chrono::high_resolution_clock::now();
    vector<int> result;
    for (int r = 0; r < repeats; r++) result = two_sum(nums, target);
    auto end = chrono::high_resolution_clock::now();
    double ms = chrono::duration<double,milli>(end - start).count() / repeats;
    bool ok = result.size() == 2 && nums[result[0]] + nums[result[1]] == target;
    cout << "{\\"n\\":" << n << ",\\"ms\\":" << ms << ",\\"ok\\":" << (ok?"true":"false") << "}" << endl;
    return 0;
}
""",
    "max_subarray": """
#include <iostream>
#include <vector>
#include <chrono>
#include <algorithm>
#include <cstdlib>
using namespace std;
// USER_CODE
int main() {
    srand(42 + N_VAL);
    int n = N_VAL;
    vector<int> nums(n);
    for (auto& x : nums) x = rand() % 201 - 100;
    int best = nums[0], cur = nums[0];
    for (int k=1;k<n;k++) { cur = max(nums[k], cur+nums[k]); best = max(best,cur); }
    int repeats = max(1, min(2000, 200000 / n));
    max_subarray(nums); // warmup
    auto start = chrono::high_resolution_clock::now();
    int result = 0;
    for (int r = 0; r < repeats; r++) result = max_subarray(nums);
    auto end = chrono::high_resolution_clock::now();
    double ms = chrono::duration<double,milli>(end - start).count() / repeats;
    bool ok = result == best;
    cout << "{\\"n\\":" << n << ",\\"ms\\":" << ms << ",\\"ok\\":" << (ok?"true":"false") << "}" << endl;
    return 0;
}
""",
    "bubble_sort": """
#include <iostream>
#include <vector>
#include <chrono>
#include <algorithm>
#include <cstdlib>
using namespace std;
// USER_CODE
int main() {
    srand(42 + N_VAL);
    int n = N_VAL;
    vector<int> nums(n);
    for (auto& x : nums) x = rand() % 2001 - 1000;
    vector<int> expected = nums;
    sort(expected.begin(), expected.end());
    int repeats = max(1, min(500, 50000 / n));
    sort_array(nums); // warmup (takes copy so nums unchanged)
    auto start = chrono::high_resolution_clock::now();
    vector<int> result;
    for (int r = 0; r < repeats; r++) result = sort_array(nums);
    auto end = chrono::high_resolution_clock::now();
    double ms = chrono::duration<double,milli>(end - start).count() / repeats;
    bool ok = result == expected;
    cout << "{\\"n\\":" << n << ",\\"ms\\":" << ms << ",\\"ok\\":" << (ok?"true":"false") << "}" << endl;
    return 0;
}
""",
}


# ── Java harnesses ────────────────────────────────────────────────────────────

JAVA_HARNESSES = {
    "two_sum": """
import java.util.*;
// USER_CODE
public class Solution {
    public static void main(String[] args) {
        Random rng = new Random(42 + N_VAL);
        int n = N_VAL;
        int[] nums = new int[n];
        for (int k=0;k<n-2;k++) nums[k] = rng.nextInt(1999) - 999;
        nums[n-2] = 10001; nums[n-1] = 10002;
        int target = 20003;
        int repeats = Math.max(1, Math.min(2000, 200000 / n));
        twoSum(nums, target); // warmup
        long start = System.nanoTime();
        int[] result = null;
        for (int r = 0; r < repeats; r++) result = twoSum(nums, target);
        double ms = (System.nanoTime() - start) / 1e6 / repeats;
        boolean ok = result != null && result.length == 2 && nums[result[0]] + nums[result[1]] == target;
        System.out.println("{\\"n\\":" + n + ",\\"ms\\":" + ms + ",\\"ok\\":" + ok + "}");
    }
}
""",
    "max_subarray": """
import java.util.*;
// USER_CODE
public class Solution {
    public static void main(String[] args) {
        Random rng = new Random(42 + N_VAL);
        int n = N_VAL;
        int[] nums = new int[n];
        for (int k=0;k<n;k++) nums[k] = rng.nextInt(201) - 100;
        int best = nums[0], cur = nums[0];
        for (int k=1;k<n;k++) { cur = Math.max(nums[k], cur+nums[k]); best = Math.max(best,cur); }
        int repeats = Math.max(1, Math.min(2000, 200000 / n));
        maxSubarray(nums); // warmup
        long start = System.nanoTime();
        int result = 0;
        for (int r = 0; r < repeats; r++) result = maxSubarray(nums);
        double ms = (System.nanoTime() - start) / 1e6 / repeats;
        System.out.println("{\\"n\\":" + n + ",\\"ms\\":" + ms + ",\\"ok\\":" + (result==best) + "}");
    }
}
""",
    "bubble_sort": """
import java.util.*;
// USER_CODE
public class Solution {
    public static void main(String[] args) {
        Random rng = new Random(42 + N_VAL);
        int n = N_VAL;
        int[] nums = new int[n];
        for (int k=0;k<n;k++) nums[k] = rng.nextInt(2001) - 1000;
        int[] expected = nums.clone();
        Arrays.sort(expected);
        int repeats = Math.max(1, Math.min(500, 50000 / n));
        sortArray(nums.clone()); // warmup
        long start = System.nanoTime();
        int[] result = null;
        for (int r = 0; r < repeats; r++) result = sortArray(nums.clone());
        double ms = (System.nanoTime() - start) / 1e6 / repeats;
        System.out.println("{\\"n\\":" + n + ",\\"ms\\":" + ms + ",\\"ok\\":" + Arrays.equals(result,expected) + "}");
    }
}
""",
}


# ── Benchmark runners ─────────────────────────────────────────────────────────

def run_benchmark_step(user_code: str, language: str, problem_id: str, n: int):
    if language == "python":
        problem = PROBLEMS[problem_id]
        harness = make_python_harness(user_code, problem, n)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(harness)
            path = f.name
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=10)
        out = proc.stdout.strip()

    elif language == "cpp":
        template = CPP_HARNESSES.get(problem_id, "")
        full = template.replace("// USER_CODE", user_code).replace("N_VAL", str(n))
        tmpdir = tempfile.mkdtemp()
        src = os.path.join(tmpdir, "sol.cpp")
        binary = os.path.join(tmpdir, "sol")
        with open(src, "w") as f:
            f.write(full)
        cp = subprocess.run(["g++", "-O2", "-std=c++17", "-o", binary, src],
                            capture_output=True, text=True, timeout=15)
        if cp.returncode != 0:
            return None, f"Compile error: {cp.stderr[:200]}"
        proc = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        out = proc.stdout.strip()

    elif language == "java":
        template = JAVA_HARNESSES.get(problem_id, "")
        full = template.replace("// USER_CODE", user_code).replace("N_VAL", str(n))
        tmpdir = tempfile.mkdtemp()
        src = os.path.join(tmpdir, "Solution.java")
        with open(src, "w") as f:
            f.write(full)
        cp = subprocess.run(["javac", src], capture_output=True, text=True, timeout=15)
        if cp.returncode != 0:
            return None, f"Compile error: {cp.stderr[:200]}"
        proc = subprocess.run(["java", "-cp", tmpdir, "Solution"],
                              capture_output=True, text=True, timeout=10)
        out = proc.stdout.strip()

    else:
        return None, "Unknown language"

    if out:
        row = json.loads(out.split("\n")[-1])
        return row, None
    return None, "No output"


def run_cpp_benchmark_with_opt(code: str, problem_id: str, n: int, opt: str):
    template = CPP_HARNESSES.get(problem_id)
    if not template:
        return None
    full = template.replace("// USER_CODE", code).replace("N_VAL", str(n))
    tmpdir = tempfile.mkdtemp()
    src = os.path.join(tmpdir, "sol.cpp")
    binary = os.path.join(tmpdir, "sol")
    with open(src, "w") as f:
        f.write(full)
    cp = subprocess.run(
        ["g++", opt, "-std=c++17", "-o", binary, src],
        capture_output=True, text=True, timeout=15
    )
    if cp.returncode != 0:
        return None
    proc = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    out = proc.stdout.strip()
    if out:
        try:
            return json.loads(out.split("\n")[-1])
        except Exception:
            return None
    return None


# ── Complexity detection ──────────────────────────────────────────────────────

def detect_complexity(bench_results):
    """
    Detect time complexity via log-log linear regression.

    In log space: log(ms) = slope * log(n) + c
    The slope is the exponent:  O(n) → slope≈1,  O(n²) → slope≈2,  O(1) → slope≈0
    This is far more robust than linear-space fitting because constant factors
    cancel out and the signal is visible even when absolute timings are tiny.
    """
    points = [
        (r["n"], r["ms"]) for r in bench_results
        if r.get("ms") is not None and r.get("ok") and r["ms"] > 1e-7
    ]
    if len(points) < 3:
        return None

    log_ns = [math.log2(p[0]) for p in points]
    log_ms = [math.log2(p[1]) for p in points]
    n_pts  = len(points)

    mean_x = sum(log_ns) / n_pts
    mean_y = sum(log_ms) / n_pts
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(log_ns, log_ms))
    den = sum((x - mean_x) ** 2 for x in log_ns)
    if den < 1e-10:
        return None
    slope = num / den

    # R² measures how well a straight line fits in log-log space
    intercept = mean_y - slope * mean_x
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(log_ns, log_ms))
    ss_tot = sum((y - mean_y) ** 2 for y in log_ms)
    r2 = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 1e-10 else 0.0

    # Map slope to the nearest complexity class
    CLASSES = [
        ("O(1)",       0.0),
        ("O(log n)",   0.35),
        ("O(n)",       1.0),
        ("O(n log n)", 1.15),
        ("O(n²)",      2.0),
        ("O(n³)",      3.0),
    ]
    best_label = min(CLASSES, key=lambda c: abs(slope - c[1]))[0]

    # Build a ranked display table: score = 1 - normalised distance from slope
    dists = [{"label": lbl, "dist": abs(slope - exp)} for lbl, exp in CLASSES]
    dists.sort(key=lambda x: x["dist"])
    max_dist = dists[-1]["dist"] or 1.0
    fits = [{"label": d["label"], "score": round(1.0 - d["dist"] / max_dist, 3)}
            for d in dists[:4]]

    return {
        "best":       best_label,
        "slope":      round(slope, 2),
        "confidence": min(99, max(50, int(r2 * 99))),
        "fits":       fits,
    }


# ── Top-level entry point ─────────────────────────────────────────────────────

def benchmark_solution(user_code: str, problem_id: str, language: str = "python") -> dict:
    results = []
    error = None
    timeout_risk = None

    for n in INPUT_SIZES:
        # After 3 data points, predict whether the next step will massively timeout
        if len(results) >= 3:
            pred = predict_next(results, n)
            if pred and pred["will_timeout"]:
                timeout_risk = {"at_n": n, "predicted_ms": pred["predicted_ms"]}
                error = f"Predicted timeout at n={n} (~{pred['predicted_ms']:.0f}ms)"
                break

        try:
            row, err = run_benchmark_step(user_code, language, problem_id, n)
            if err:
                results.append({"n": n, "ms": None, "ok": False, "err": err})
                error = err
                break
            if row:
                results.append(row)
                if row["ms"] is None or row["ms"] > 4000:
                    error = row.get("err", "Timeout")
                    break
        except Exception as e:
            results.append({"n": n, "ms": None, "ok": False, "err": str(e)})
            error = str(e)
            break

    approach = _clusterer.predict(problem_id, user_code)
    _clusterer.add(problem_id, user_code)

    return {
        "results": results,
        "error": error,
        "complexity": detect_complexity(results),
        "approach": approach,
        "timeout_risk": timeout_risk,
    }
