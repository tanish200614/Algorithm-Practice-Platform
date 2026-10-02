// Starter code per problem and language. The benchmark harness calls these
// exact function names, so renaming one breaks the harness for that language.
export const STARTERS = {
  two_sum: {
    python: `def two_sum(nums: list, target: int) -> list:\n    pass`,
    cpp: `#include <iostream>\n#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nvector<int> two_sum(vector<int>& nums, int target) {\n    // your code here\n    return {};\n}`,
    java: `static int[] twoSum(int[] nums, int target) {\n    // your code here\n    return new int[]{};\n}`,
  },
  max_subarray: {
    python: `def max_subarray(nums: list) -> int:\n    pass`,
    cpp: `#include <iostream>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n\nint max_subarray(vector<int>& nums) {\n    // your code here\n    return 0;\n}`,
    java: `static int maxSubarray(int[] nums) {\n    // your code here\n    return 0;\n}`,
  },
  bubble_sort: {
    python: `def sort_array(nums: list) -> list:\n    pass`,
    cpp: `#include <iostream>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n\nvector<int> sort_array(vector<int> nums) {\n    // your code here\n    return nums;\n}`,
    java: `static int[] sortArray(int[] nums) {\n    // your code here\n    return nums;\n}`,
  },
};

export const LANGUAGE_LABELS = { python: "Python", cpp: "C++", java: "Java" };

export function starterFor(problemId, language) {
  return STARTERS[problemId]?.[language] ?? "";
}
