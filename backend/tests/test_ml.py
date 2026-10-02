from ml import DifficultyEstimator, EloTracker, SolutionClusterer, code_similarity, label_approach


class TestElo:
    def test_solving_raises_skill_and_eases_the_problem(self):
        elo = EloTracker()
        before_skill = elo.get_skill("ada")
        before_difficulty = elo.get_difficulty("two_sum")

        elo.update("ada", "two_sum", solved=True)

        assert elo.get_skill("ada") > before_skill
        assert elo.get_difficulty("two_sum") < before_difficulty

    def test_failing_lowers_skill(self):
        elo = EloTracker()
        elo.update("ada", "two_sum", solved=False)
        assert elo.get_skill("ada") < EloTracker.DEFAULT

    def test_beating_a_hard_problem_is_worth_more(self):
        """An upset should move the rating further than an expected win."""
        easy = EloTracker()
        easy._difficulties["two_sum"] = 600
        easy_gain = easy.update("ada", "two_sum", solved=True)

        hard = EloTracker()
        hard._difficulties["two_sum"] = 1600
        hard_gain = hard.update("ada", "two_sum", solved=True)

        assert hard_gain > easy_gain

    def test_recommends_the_problem_nearest_the_players_skill(self):
        elo = EloTracker()
        elo._skills["ada"] = 1100
        assert elo.recommend("ada", ["two_sum", "max_subarray", "bubble_sort"]) == "max_subarray"

    def test_tiers_track_skill(self):
        elo = EloTracker()
        elo._skills["novice"] = 800
        elo._skills["expert"] = 1300
        assert elo.tier("novice") == "Beginner"
        assert elo.tier("expert") == "Expert"


class TestApproachLabelling:
    def test_hash_map_solution(self):
        code = "def f(nums, t):\n    seen = {}\n    for x in nums:\n        seen[x] = 1"
        assert label_approach(code) == "Hash Map"

    def test_nested_loops_read_as_brute_force(self):
        code = "def f(n):\n    for i in n:\n        for j in n:\n            pass"
        assert label_approach(code) == "Brute Force"

    def test_two_pointer_solution(self):
        code = "def f(a):\n    left = 0\n    right = len(a) - 1\n    while left < right:\n        left += 1"
        assert label_approach(code) == "Two Pointer"


class TestClusterer:
    def test_untrained_clusterer_still_labels(self):
        c = SolutionClusterer()
        out = c.predict("two_sum", "seen = {}")
        assert out["label"] == "Hash Map"
        assert out["similar_count"] == 0

    def test_training_kicks_in_and_counts_similar_submissions(self):
        c = SolutionClusterer()
        for _ in range(4):
            c.add("two_sum", "def f(nums):\n    seen = {}\n    for x in nums:\n        seen[x] = 1")
        for _ in range(4):
            c.add("two_sum", "def f(n):\n    for i in n:\n        for j in n:\n            pass")

        assert c._trained
        out = c.predict("two_sum", "def f(nums):\n    seen = {}\n    for x in nums:\n        seen[x] = 1")
        assert out["total_seen"] == 8
        assert out["similar_count"] > 0


class TestCodeSimilarity:
    def test_identical_code_scores_one(self):
        assert code_similarity("def f(): return 1", "def f(): return 1") == 1.0

    def test_whitespace_is_ignored(self):
        assert code_similarity("def f():\n    return 1", "def  f():\treturn 1") == 1.0

    def test_unrelated_code_scores_low(self):
        score = code_similarity(
            "def two_sum(nums, t):\n    seen = {}",
            "class Widget:\n    def render(self):\n        paint()",
        )
        assert score < 0.3

    def test_empty_input_is_not_a_match(self):
        assert code_similarity("", "def f(): pass") == 0.0


class TestDifficultyBlending:
    """The estimator is meant to shift from text heuristics toward observed
    ELO as evidence accumulates."""

    DESC = ("Given a list of integers and a target, return the indices of two "
            "numbers that add up to the target.")

    def test_a_problem_everyone_fails_is_reported_harder(self):
        """_solve_counts is keyed by player, so looking up a problem id always
        returned 0 and the score never moved off the text heuristic."""
        elo, est = EloTracker(), DifficultyEstimator()
        before = est.score(self.DESC, "two_sum", elo)["score"]

        for i in range(40):
            elo.update(f"p{i}", "two_sum", solved=False)

        after = est.score(self.DESC, "two_sum", elo)["score"]
        assert elo.get_difficulty("two_sum") > 1200
        assert after > before

    def test_attempts_count_the_problem_not_the_player(self):
        elo = EloTracker()
        elo.update("ada", "two_sum", solved=True)
        elo.update("bob", "two_sum", solved=False)
        assert elo.get_attempts("two_sum") == 2
        assert elo._solve_counts["ada"] == 1

    def test_one_attempt_barely_moves_the_estimate(self):
        """Weight ramps with evidence, so a single result must not swing it."""
        elo, est = EloTracker(), DifficultyEstimator()
        before = est.score(self.DESC, "two_sum", elo)["score"]
        elo.update("ada", "two_sum", solved=False)
        assert abs(est.score(self.DESC, "two_sum", elo)["score"] - before) <= 1
