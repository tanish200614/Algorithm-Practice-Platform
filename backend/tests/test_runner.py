"""Ad-hoc "Test Run" execution: the scaffolding that wraps a bare
submission into something the toolchain will accept."""

import pytest

from runner import prepare_java_source, run_java


class TestJavaScaffold:
    """The scaffold has to produce something that actually compiles."""

    def test_a_solution_using_collections_compiles(self):
        """java.util is not imported by default, so a HashMap solution — which
        is what nearly every real Two Sum answer looks like — failed to compile
        with 'cannot find symbol' until the scaffold imported it."""
        code = (
            "static int[] twoSum(int[] nums, int target) {\n"
            "    HashMap<Integer,Integer> seen = new HashMap<>();\n"
            "    for (int i = 0; i < nums.length; i++) {\n"
            "        Integer j = seen.get(target - nums[i]);\n"
            "        if (j != null) return new int[]{j, i};\n"
            "        seen.put(nums[i], i);\n"
            "    }\n"
            "    return new int[]{-1, -1};\n"
            "}"
        )
        res = run_java(code)
        assert not res["compile_error"], res["stderr"]

    def test_a_submission_bringing_its_own_class_keeps_that_name(self):
        source, name = prepare_java_source("public class Racer { }")
        assert name == "Racer"
        assert source == "public class Racer { }"

    def test_a_bare_method_is_wrapped_in_Solution(self):
        source, name = prepare_java_source("static int f() { return 1; }")
        assert name == "Solution"
        assert "public class Solution" in source
        assert "import java.util.*;" in source
