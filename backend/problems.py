import shutil

from sandbox import docker_available


def detect_compiler(name):
    return shutil.which(name) is not None


def language_available(lang_id: str) -> bool:
    """
    A language is usable if the sandbox can run it. With Docker up that means
    the image exists; on the host fallback it means the toolchain is installed
    locally. Checked per request rather than at import, so building the images
    or starting the daemon takes effect without a backend restart.
    """
    compiler = LANGUAGES[lang_id].get("compiler")
    if compiler is None:
        return True
    return docker_available(lang_id) or detect_compiler(compiler)

PROBLEMS = {
    "two_sum": {
        "id": "two_sum",
        "title": "Two Sum",
        "description": "Given a list of integers and a target, return the indices of two numbers that add up to the target.",
        "function_name": "two_sum",
        "signature": "def two_sum(nums: list, target: int) -> list:",
        "input_generator": """
import random
def gen(n):
    # Values in [-999, 999] so no two random values can sum to 20003.
    # The answer is forced to be the last two elements, ensuring both
    # brute-force (O(n²)) and hash-map (O(n)) solutions must scan the
    # full array before finding the pair.
    nums = [random.randint(-999, 999) for _ in range(n - 2)]
    nums.append(10001)
    nums.append(10002)
    target = 20003
    return (nums, target)
""",
        "validator": """
def validate(result, nums, target):
    if not isinstance(result, list) or len(result) != 2:
        return False
    i, j = result
    return nums[i] + nums[j] == target
""",
    },
    "max_subarray": {
        "id": "max_subarray",
        "title": "Maximum Subarray",
        "description": "Find the contiguous subarray with the largest sum and return its sum.",
        "function_name": "max_subarray",
        "signature": "def max_subarray(nums: list) -> int:",
        "input_generator": """
import random
def gen(n):
    nums = [random.randint(-100, 100) for _ in range(n)]
    return (nums,)
""",
        "validator": """
def validate(result, nums):
    best = cur = nums[0]
    for x in nums[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return result == best
""",
    },
    "bubble_sort": {
        "id": "bubble_sort",
        "title": "Sort the Array",
        "description": "Sort a list of integers in ascending order. Return the sorted list.",
        "function_name": "sort_array",
        "signature": "def sort_array(nums: list) -> list:",
        "input_generator": """
import random
def gen(n):
    nums = [random.randint(-1000, 1000) for _ in range(n)]
    return (nums,)
""",
        "validator": """
def validate(result, nums):
    return result == sorted(nums)
""",
    },
}

LANGUAGES = {
    "python": {
        "label": "Python 3",
        "extension": ".py",
        "compiler": None,
    },
    "cpp": {
        "label": "C++17",
        "extension": ".cpp",
        "compiler": "g++",
    },
    "java": {
        "label": "Java",
        "extension": ".java",
        "compiler": "javac",
    },
}
