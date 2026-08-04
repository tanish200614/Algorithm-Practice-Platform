"""
Generated-problem validation.

The point of the pipeline is that a model's problem is not trusted until its
reference solution has been observed to satisfy its own test cases. These
tests feed it problems that are broken in the ways generation actually breaks.
"""

import pytest

from generator import MIN_TEST_CASES, PROBLEM_SCHEMA, validate_problem

REFERENCE = (
    "def count_pairs(nums, k):\n"
    "    seen = {}\n"
    "    total = 0\n"
    "    for v in nums:\n"
    "        total += seen.get(k - v, 0)\n"
    "        seen[v] = seen.get(v, 0) + 1\n"
    "    return total"
)

GOOD = {
    "id": "count_pairs",
    "title": "Count Pairs",
    "description": "Count pairs summing to k.",
    "function_name": "count_pairs",
    "signature": "def count_pairs(nums, k):",
    "reference_solution": REFERENCE,
    "test_cases": [
        {"args": "[[1,2,3,4],5]", "expected": "2"},
        {"args": "[[1,1,1],2]", "expected": "3"},
        {"args": "[[],5]", "expected": "0"},
        {"args": "[[5],5]", "expected": "0"},
    ],
}


class TestSchema:
    def test_strict_mode_forbids_extra_fields(self):
        """strict json_schema is what makes the model's output shape a
        guarantee instead of something to defensively parse."""
        assert PROBLEM_SCHEMA["additionalProperties"] is False
        assert "reference_solution" in PROBLEM_SCHEMA["required"]


class TestValidation:
    def test_a_self_consistent_problem_is_accepted(self):
        ok, report = validate_problem(GOOD)
        assert ok, report
        assert report["cases_passed"] == len(GOOD["test_cases"])

    def test_a_wrong_reference_solution_is_rejected(self):
        """The failure that reading the JSON cannot catch: the solution looks
        plausible and does not satisfy the problem's own tests."""
        broken = {**GOOD, "reference_solution": REFERENCE.replace(
            "total += seen.get(k - v, 0)", "total += seen.get(k - v, 0) + 1")}
        ok, report = validate_problem(broken)
        assert not ok
        assert report["stage"] == "tests"

    def test_a_hallucinated_expected_value_is_rejected(self):
        wrong = {**GOOD, "test_cases": [{"args": "[[1,2,3,4],5]", "expected": "7"}]
                 + GOOD["test_cases"][1:]}
        ok, report = validate_problem(wrong)
        assert not ok
        assert report["stage"] == "tests"

    def test_a_reference_that_raises_is_rejected(self):
        boom = {**GOOD, "reference_solution":
                "def count_pairs(nums, k):\n    return nums[99]"}
        assert not validate_problem(boom)[0]

    def test_a_missing_function_is_caught_before_execution(self):
        """Cheap static check, so an obviously broken problem never reaches
        the sandbox."""
        ok, report = validate_problem({**GOOD, "function_name": "solve"})
        assert not ok
        assert report["stage"] == "shape"

    def test_too_few_test_cases_is_rejected(self):
        thin = {**GOOD, "test_cases": GOOD["test_cases"][:MIN_TEST_CASES - 1]}
        ok, report = validate_problem(thin)
        assert not ok
        assert report["stage"] == "shape"

    @pytest.mark.parametrize("bad_id", ["CountPairs", "2sum", "count-pairs", ""])
    def test_ids_must_be_snake_case(self, bad_id):
        assert not validate_problem({**GOOD, "id": bad_id})[0]

    def test_unparsable_arguments_are_rejected(self):
        junk = {**GOOD, "test_cases": [{"args": "not json", "expected": "0"}]
                + GOOD["test_cases"][1:]}
        assert not validate_problem(junk)[0]
