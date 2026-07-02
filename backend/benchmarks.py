import json, math, re

from problems import PROBLEMS
from ml import clusterer as _clusterer, predict_next
from runner import prepare_java_source
from sandbox import (
    cpp_compile_and_run,
    cpp_compile_to_asm,
    java_compile_and_run,
    java_compile_to_bytecode,
    run_sandboxed,
)

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
// The containers a solution is likely to reach for. libc++ pulls several of
// these in transitively, so a missing include only fails on the Linux
// (libstdc++) sandbox and not on a macOS dev machine.
#include <unordered_map>
#include <unordered_set>
#include <map>
#include <set>
#include <queue>
#include <stack>
#include <string>
#include <numeric>
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
// The containers a solution is likely to reach for. libc++ pulls several of
// these in transitively, so a missing include only fails on the Linux
// (libstdc++) sandbox and not on a macOS dev machine.
#include <unordered_map>
#include <unordered_set>
#include <map>
#include <set>
#include <queue>
#include <stack>
#include <string>
#include <numeric>
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
// The containers a solution is likely to reach for. libc++ pulls several of
// these in transitively, so a missing include only fails on the Linux
// (libstdc++) sandbox and not on a macOS dev machine.
#include <unordered_map>
#include <unordered_set>
#include <map>
#include <set>
#include <queue>
#include <stack>
#include <string>
#include <numeric>
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
public class Solution {
    // USER_CODE
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
public class Solution {
    // USER_CODE
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
public class Solution {
    // USER_CODE
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

def _fill(template: str, user_code: str, n: int) -> str:
    return template.replace("// USER_CODE", user_code).replace("N_VAL", str(n))


def _sandbox_error(res) -> str:
    """Turn a failed sandbox run into a message worth showing the player."""
    if res.compile_failed:
        return f"Compile error: {res.stderr.strip()[:200]}"
    if res.timed_out:
        return "Timed out"
    if res.oom_killed:
        return "Exceeded the memory limit"
    return (res.stderr.strip() or "Execution failed")[:200]


def _parse_row(res):
    """Harnesses print one JSON object on the last line of stdout."""
    out = res.stdout.strip()
    if not out:
        return None, _sandbox_error(res)
    try:
        return json.loads(out.split("\n")[-1]), None
    except (ValueError, IndexError):
        return None, _sandbox_error(res)


def run_benchmark_step(user_code: str, language: str, problem_id: str, n: int):
    if language == "python":
        problem = PROBLEMS[problem_id]
        harness = make_python_harness(user_code, problem, n)
        res = run_sandboxed("python", {"harness.py": harness}, ["harness.py"])

    elif language == "cpp":
        template = CPP_HARNESSES.get(problem_id)
        if not template:
            return None, f"No C++ harness for problem '{problem_id}'"
        res = run_sandboxed(
            "cpp",
            {"solution.cpp": _fill(template, user_code, n)},
            cpp_compile_and_run(),
        )

    elif language == "java":
        template = JAVA_HARNESSES.get(problem_id)
        if not template:
            return None, f"No Java harness for problem '{problem_id}'"
        res = run_sandboxed(
            "java",
            {"Solution.java": _fill(template, user_code, n)},
            java_compile_and_run(),
        )

    else:
        return None, "Unknown language"

    if not res.ok:
        return None, _sandbox_error(res)
    return _parse_row(res)


def run_cpp_benchmark_with_opt(code: str, problem_id: str, n: int, opt: str):
    """Same benchmark at a chosen optimisation level, for the -O0/-O2 compare."""
    template = CPP_HARNESSES.get(problem_id)
    if not template:
        return None
    res = run_sandboxed(
        "cpp",
        {"solution.cpp": _fill(template, code, n)},
        cpp_compile_and_run(opt=opt),
    )
    if not res.ok:
        return None
    row, _ = _parse_row(res)
    return row


ASM_SCAFFOLD = """\
#include <iostream>
#include <vector>
#include <algorithm>
#include <unordered_map>
#include <string>
using namespace std;

{code}

int main() {{ return 0; }}
"""


def compile_to_assembly(code: str, opt: str = "-O2"):
    """
    Compile a C++ solution to annotated assembly inside the sandbox.

    Returns (assembly_text, error). Intel syntax is preferred for readability
    but is x86-only, so fall back to the toolchain default on other
    architectures rather than failing outright.
    """
    source = code if "int main(" in code else ASM_SCAFFOLD.format(code=code)

    last_error = None
    for intel in (True, False):
        res = run_sandboxed(
            "cpp",
            {"solution.cpp": source},
            cpp_compile_to_asm(opt=opt, intel=intel),
        )
        if res.ok and res.stdout.strip():
            return res.stdout, None
        last_error = _sandbox_error(res)

    return None, last_error


# ── Java bytecode viewer ──────────────────────────────────────────────────────

# No main method: javap only needs a compiled class, and main's bytecode
# would be noise on top of the method actually being read.
JAVA_BYTECODE_SCAFFOLD = """\
import java.util.*;

public class Solution {{
{code}
}}
"""

_METHOD_RE = re.compile(r"^ {2}(\S.*?);\s*$")
_INSTR_RE = re.compile(r"^\s+(\d+):\s+(\S+)")

# Opcodes worth calling out, and why a reader should care.
_BOXING = ("Integer.valueOf", "Long.valueOf", "Double.valueOf", "Character.valueOf",
           "Boolean.valueOf", "Float.valueOf", "Short.valueOf", "Byte.valueOf")
_UNBOXING = (".intValue", ".longValue", ".doubleValue", ".charValue",
             ".booleanValue", ".floatValue")


def compile_to_bytecode(code: str):
    """
    Compile a Java submission and disassemble it. Returns (listing, error).
    """
    source, class_name = prepare_java_source(code, JAVA_BYTECODE_SCAFFOLD)
    res = run_sandboxed(
        "java",
        {f"{class_name}.java": source},
        java_compile_to_bytecode(class_name),
    )
    if res.ok and res.stdout.strip():
        return res.stdout, None
    return None, _sandbox_error(res)


def _method_blocks(listing: str) -> list:
    """
    Split a javap listing into (signature, lines) per method.

    The constructor javac synthesises is dropped here rather than at each
    call site: it is scaffolding, and counting its invokespecial made a
    submission of pure arithmetic report a method invocation it never made.
    """
    blocks, current = [], None
    for line in listing.splitlines():
        m = _METHOD_RE.match(line)
        if m and not line.strip().startswith("Compiled from"):
            current = {"signature": m.group(1).strip(), "lines": []}
            blocks.append(current)
            continue
        if current is not None:
            current["lines"].append(line)

    return [
        b for b in blocks
        if not b["signature"].endswith("Solution()")
        and any(_INSTR_RE.match(l) for l in b["lines"])
    ]


def parse_bytecode_methods(listing: str) -> list:
    """Per-method instruction counts, so size differences are visible at a
    glance instead of being counted by hand."""
    return [
        {
            "signature": b["signature"],
            "instructions": sum(1 for l in b["lines"] if _INSTR_RE.match(l)),
        }
        for b in _method_blocks(listing)
    ]


def bytecode_insights(listing: str) -> list:
    """
    The few facts in a javap listing that actually teach something. Reading
    raw bytecode is a skill; pointing at the costly parts is the useful half.

    Only the submission's own methods are considered, so the synthesised
    constructor cannot contribute counts the player did not write.
    """
    blocks = _method_blocks(listing)
    listing = "\n".join(l for b in blocks for l in b["lines"]) if blocks else listing
    out = []

    boxes = sum(listing.count(sym) for sym in _BOXING)
    if boxes:
        out.append({
            "label": f"{boxes} autoboxing conversion{'s' if boxes != 1 else ''}",
            "detail": "Each Integer.valueOf allocates (or interns) a wrapper "
                      "object. Inside a hot loop this is the usual reason a "
                      "Java solution trails an equivalent C++ one.",
        })

    unboxes = sum(listing.count(sym) for sym in _UNBOXING)
    if unboxes:
        out.append({
            "label": f"{unboxes} unboxing call{'s' if unboxes != 1 else ''}",
            "detail": "Unwrapping a boxed value back to a primitive. Paired "
                      "with the boxing above, this is the cost of using a "
                      "Map<Integer,Integer> instead of an int[].",
        })

    if "makeConcatWithConstants" in listing:
        out.append({
            "label": "String concatenation via invokedynamic",
            "detail": "javac compiles + on strings to an indy call. In a loop "
                      "that builds a new string every iteration — a StringBuilder "
                      "kept outside the loop avoids it.",
        })

    if "java/lang/StringBuilder" in listing:
        out.append({
            "label": "StringBuilder allocated",
            "detail": "Check whether it is created inside a loop. One per "
                      "iteration defeats the point of using it at all.",
        })

    invokes = sum(listing.count(op) for op in
                  ("invokevirtual", "invokestatic", "invokeinterface", "invokespecial"))
    if invokes:
        out.append({
            "label": f"{invokes} method invocation{'s' if invokes != 1 else ''}",
            "detail": "The JIT inlines most of these at runtime, so the count "
                      "is an upper bound on what actually executes as a call.",
        })

    return out


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
