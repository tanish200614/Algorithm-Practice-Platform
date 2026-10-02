"""
Java bytecode viewer.

Parsing and the insight rules run anywhere; the tests that need a real javac
skip when no Java toolchain is reachable.
"""

import pytest

from benchmarks import bytecode_insights, compile_to_bytecode, parse_bytecode_methods
from problems import language_available

requires_java = pytest.mark.skipif(
    not language_available("java"),
    reason="no Java toolchain (no sandbox image and no local javac)",
)

TWO_SUM = """\
static int[] twoSum(int[] nums, int target) {
    HashMap<Integer,Integer> seen = new HashMap<>();
    for (int i = 0; i < nums.length; i++) {
        Integer j = seen.get(target - nums[i]);
        if (j != null) return new int[]{j, i};
        seen.put(nums[i], i);
    }
    return new int[]{-1, -1};
}"""

# A javap listing, so the parser can be tested without invoking a compiler.
SAMPLE = """\
Compiled from "Solution.java"
public class Solution {
  public Solution();
    Code:
       0: aload_0
       1: invokespecial #1
       4: return

  static int add(int, int);
    Code:
       0: iload_0
       1: iload_1
       2: iadd
       3: ireturn
}
"""


class TestParsing:
    def test_counts_instructions_per_method(self):
        methods = parse_bytecode_methods(SAMPLE)
        assert len(methods) == 1
        assert methods[0]["signature"] == "static int add(int, int)"
        assert methods[0]["instructions"] == 4

    def test_the_implicit_constructor_is_not_shown(self):
        """javac adds a no-arg constructor. The player didn't write it, so
        don't list it."""
        assert all("Solution()" not in m["signature"] for m in parse_bytecode_methods(SAMPLE))

    def test_a_listing_with_no_methods_yields_nothing(self):
        assert parse_bytecode_methods("Compiled from \"X.java\"\npublic class X {\n}\n") == []


class TestInsights:
    def test_boxing_is_reported(self):
        insights = bytecode_insights("invokestatic Integer.valueOf ... Integer.valueOf")
        assert any("autoboxing" in i["label"] for i in insights)

    def test_string_concatenation_is_reported(self):
        insights = bytecode_insights("invokedynamic makeConcatWithConstants")
        assert any("concatenation" in i["label"] for i in insights)

    def test_clean_primitive_code_reports_no_boxing(self):
        """An int[]-only solution should not be told it is boxing."""
        insights = bytecode_insights("0: iload_0\n1: iadd\n2: ireturn")
        assert not any("autoboxing" in i["label"] for i in insights)


@requires_java
class TestCompilation:
    def test_a_real_solution_disassembles(self):
        listing, err = compile_to_bytecode(TWO_SUM)
        assert err is None
        assert "twoSum" in listing
        assert "Code:" in listing

    def test_a_hashmap_solution_shows_its_boxing(self):
        """Map<Integer,Integer> boxing is the usual reason a Java answer is
        slower than C++, so the viewer should point it out."""
        listing, _ = compile_to_bytecode(TWO_SUM)
        assert any("autoboxing" in i["label"] for i in bytecode_insights(listing))

    def test_a_compile_error_is_reported_not_raised(self):
        listing, err = compile_to_bytecode("static int f() { this is not java }")
        assert listing is None
        assert "Compile error" in err


class TestInsightScoping:
    def test_the_synthetic_constructor_contributes_no_counts(self):
        """javac's implicit constructor has an invokespecial. Counting it made
        pure arithmetic look like it called a method."""
        insights = bytecode_insights(SAMPLE)
        assert not any("invocation" in i["label"] for i in insights)
