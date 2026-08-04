"""
Problem generation, with every generated problem executed before it is trusted.

A model asked for a coding problem will happily return one whose reference
solution does not satisfy its own test cases, or whose expected outputs were
reasoned about rather than computed. Neither failure is visible by reading the
JSON — the only way to find it is to run the thing.

So generation is a pipeline, not a call: the model proposes, the reference
solution is executed against the proposed tests inside the same sandbox that
runs player submissions, and anything that disagrees with itself is rejected
and regenerated. What reaches the problem set has been observed to work.
"""

import json
import re

from llm import structured
from sandbox import run_sandboxed

MIN_TEST_CASES = 4

# strict json_schema requires every property listed in `required` and forbids
# additionalProperties, so the shape below is a guarantee rather than a hope.
# args/expected are JSON-encoded strings because a test case's arguments are
# arbitrarily typed, which strict mode cannot express directly.
PROBLEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "title", "description", "function_name", "signature",
                 "reference_solution", "test_cases"],
    "properties": {
        "id": {"type": "string", "description": "snake_case identifier"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "function_name": {"type": "string"},
        "signature": {"type": "string"},
        "reference_solution": {
            "type": "string",
            "description": "Complete Python function, correct and self-contained.",
        },
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["args", "expected"],
                "properties": {
                    "args": {"type": "string",
                             "description": "JSON array of positional arguments"},
                    "expected": {"type": "string",
                                 "description": "JSON-encoded expected return value"},
                },
            },
        },
    },
}

_SYSTEM = """\
You write algorithm practice problems.

Rules:
- The reference solution must be correct, self-contained Python, and must
  define exactly the function named in function_name.
- Every expected value must be what the reference solution actually returns
  for those arguments. Compute it, do not estimate it.
- args is a JSON array of positional arguments. expected is the JSON-encoded
  return value.
- Prefer problems where a naive and an optimal approach differ in complexity,
  since solutions are graded on how they scale."""


def _harness(problem: dict) -> str:
    """Run the reference solution against every proposed test case."""
    return (
        "import json\n"
        f"{problem['reference_solution']}\n"
        f"CASES = {json.dumps(problem['test_cases'])}\n"
        "out = []\n"
        "for c in CASES:\n"
        "    try:\n"
        "        args = json.loads(c['args'])\n"
        "        expected = json.loads(c['expected'])\n"
        "    except Exception as e:\n"
        "        out.append({'ok': False, 'err': 'unparsable case: ' + str(e)[:120]})\n"
        "        continue\n"
        "    try:\n"
        f"        got = {problem['function_name']}(*args)\n"
        "        out.append({'ok': got == expected, 'got': repr(got)[:120],\n"
        "                    'expected': repr(expected)[:120]})\n"
        "    except Exception as e:\n"
        "        out.append({'ok': False, 'err': type(e).__name__ + ': ' + str(e)[:120]})\n"
        "print(json.dumps(out))\n"
    )


def validate_problem(problem: dict) -> tuple:
    """
    Execute a generated problem against itself. Returns (ok, report).

    Static checks first because they are free; then the part that actually
    matters, which is running the code.
    """
    for field in PROBLEM_SCHEMA["required"]:
        if not problem.get(field):
            return False, {"stage": "shape", "error": f"missing {field}"}

    if not re.match(r"^[a-z][a-z0-9_]*$", problem["id"]):
        return False, {"stage": "shape", "error": f"id not snake_case: {problem['id']}"}

    if len(problem["test_cases"]) < MIN_TEST_CASES:
        return False, {"stage": "shape",
                       "error": f"only {len(problem['test_cases'])} test cases"}

    # A reference solution that does not define the function it claims to is
    # the most common generation failure, and it is cheap to catch here.
    if not re.search(rf"def\s+{re.escape(problem['function_name'])}\s*\(",
                     problem["reference_solution"]):
        return False, {"stage": "shape",
                       "error": f"{problem['function_name']} is not defined"}

    res = run_sandboxed("python", {"check.py": _harness(problem)}, ["check.py"])
    if not res.ok:
        return False, {"stage": "execution",
                       "error": (res.stderr or "reference solution failed to run")[:300]}

    try:
        rows = json.loads(res.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return False, {"stage": "execution", "error": "harness produced no result"}

    failures = [{"case": i, **r} for i, r in enumerate(rows) if not r.get("ok")]
    if failures:
        return False, {"stage": "tests", "failed": len(failures),
                       "of": len(rows), "examples": failures[:3]}

    return True, {"stage": "ok", "cases_passed": len(rows)}


def generate_problem(topic: str, difficulty: str = "medium", attempts: int = 3) -> dict:
    """
    Generate a problem and return it only once it has validated.

    Retries bypass the cache: a rejected problem is a deterministic output for
    that request, so asking again with caching on would return the same broken
    problem forever.
    """
    reports = []
    for attempt in range(attempts):
        problem = structured(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",
                 "content": f"Write a {difficulty} problem about {topic}."},
            ],
            PROBLEM_SCHEMA,
            name="algorithm_problem",
            # Nudge off the cached answer on a retry, and add variety.
            temperature=0.0 if attempt == 0 else 0.7,
            use_cache=(attempt == 0),
        )
        ok, report = validate_problem(problem)
        reports.append(report)
        if ok:
            problem["_validation"] = report
            return problem

    raise ValueError(f"no valid problem after {attempts} attempts: {reports}")
