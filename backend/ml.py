import math
import re
from collections import defaultdict

# ── Tokenization ───────────────────────────────────────────────────────────────

_SKIP = {
    'def', 'for', 'while', 'if', 'else', 'elif', 'return', 'import', 'from',
    'class', 'int', 'void', 'bool', 'auto', 'true', 'false', 'null', 'none',
    'new', 'this', 'static', 'public', 'private', 'using', 'namespace', 'std',
    'include', 'endl', 'cout', 'cin', 'string', 'len', 'range', 'print', 'main',
    'args', 'result', 'val', 'var', 'let', 'const', 'nums', 'num', 'target',
    'the', 'and', 'not', 'pass', 'self',
}

def _tokenize(code: str) -> list:
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', code.lower())
    return [t for t in tokens if len(t) > 2 and t not in _SKIP]


# ── Heuristic approach labeling ────────────────────────────────────────────────

_APPROACH_KEYWORDS = {
    # Only actual data-structure names/methods — not variable names like 'complement'
    "Hash Map": {
        'dict', 'hashmap', 'unordered_map', 'seen', 'memo',
        'cache', 'defaultdict', 'counter', 'hashtable',
        'treemap', 'linkedhashmap', 'put', 'getordefault',
    },
    "Two Pointer": {
        'left', 'right', 'ptr', 'pointer', 'low', 'high', 'slow', 'fast',
    },
    "Sorting": {
        'sort', 'sorted', 'mergesort', 'quicksort', 'heapsort', 'qsort',
    },
    "Brute Force": {
        'brute', 'nested', 'naive',
    },
}

def _has_nested_loops(code: str) -> bool:
    depths = []
    for line in code.splitlines():
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith(('for ', 'for(', 'while ', 'while(')):
            depths.append(indent)
    return len(depths) >= 2 and max(depths, default=0) > min(depths, default=0)

def label_approach(code: str) -> str:
    tokens = set(_tokenize(code))
    scores = {name: len(tokens & kws) for name, kws in _APPROACH_KEYWORDS.items()}
    if _has_nested_loops(code):
        scores["Brute Force"] += 3
    best, best_score = max(scores.items(), key=lambda x: x[1])
    if best_score > 0:
        return best
    return "Brute Force" if _has_nested_loops(code) else "Unknown"


# ── TF-IDF + cosine k-means solution clusterer ────────────────────────────────

class SolutionClusterer:
    """Groups submitted solutions by approach using TF-IDF + cosine k-means."""
    MIN_DOCS = 6
    N_CLUSTERS = 4
    ITERS = 25

    def __init__(self):
        self._docs: list = []
        self._heuristics: list = []
        self._vocab: list = []
        self._idf: dict = {}
        self._vecs: list = []
        self._centroids: list = []
        self._assignments: list = []
        self._trained = False

    def add(self, problem_id: str, code: str) -> str:
        tokens = _tokenize(code)
        label = label_approach(code)
        self._docs.append((problem_id, tokens))
        self._heuristics.append(label)
        if len(self._docs) >= self.MIN_DOCS:
            self._train()
        return label

    def predict(self, problem_id: str, code: str) -> dict:
        label = label_approach(code)
        total = sum(1 for pid, _ in self._docs if pid == problem_id)
        if not self._trained:
            return {"label": label, "similar_count": 0, "total_seen": total}
        vec = self._tfidf_vec(_tokenize(code))
        dists = [self._cosine_dist(vec, c) for c in self._centroids]
        cluster = dists.index(min(dists))
        cluster_labels: dict = defaultdict(int)
        for i, lbl in enumerate(self._heuristics):
            if self._assignments[i] == cluster:
                cluster_labels[lbl] += 1
        if cluster_labels:
            label = max(cluster_labels, key=cluster_labels.get)
        similar = sum(
            1 for i, (pid, _) in enumerate(self._docs)
            if pid == problem_id and self._assignments[i] == cluster
        )
        return {"label": label, "similar_count": similar, "total_seen": total}

    def _train(self):
        import random
        all_tokens = [toks for _, toks in self._docs]
        vocab = sorted({t for doc in all_tokens for t in doc})
        n = len(all_tokens)
        df: dict = defaultdict(int)
        for doc in all_tokens:
            for t in set(doc):
                df[t] += 1
        self._idf = {t: math.log((n + 1) / (df[t] + 1)) for t in vocab}
        self._vocab = vocab
        self._vecs = [self._tfidf_vec(doc) for doc in all_tokens]
        k = min(self.N_CLUSTERS, len(self._vecs))
        rng = random.Random(42)
        centroids = [list(self._vecs[i]) for i in rng.sample(range(len(self._vecs)), k)]
        assignments = []
        for _ in range(self.ITERS):
            assignments = [
                min(range(k), key=lambda ci, v=vec: self._cosine_dist(v, centroids[ci]))
                for vec in self._vecs
            ]
            new_centroids = []
            d = len(vocab)
            for ci in range(k):
                cluster = [self._vecs[j] for j in range(len(self._vecs)) if assignments[j] == ci]
                if cluster:
                    new_centroids.append([sum(v[dim] for v in cluster) / len(cluster) for dim in range(d)])
                else:
                    new_centroids.append(centroids[ci])
            if new_centroids == centroids:
                break
            centroids = new_centroids
        self._centroids = centroids
        self._assignments = assignments
        self._trained = True

    def _tfidf_vec(self, tokens: list) -> list:
        tf: dict = defaultdict(float)
        for t in tokens:
            tf[t] += 1
        total = len(tokens) or 1
        return [(tf[w] / total) * self._idf.get(w, 0.0) for w in self._vocab]

    @staticmethod
    def _cosine_dist(a: list, b: list) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na < 1e-10 or nb < 1e-10:
            return 1.0
        return 1.0 - dot / (na * nb)


# ── Early timeout prediction ───────────────────────────────────────────────────

def predict_next(partial_results: list, next_n: int) -> dict:
    """Fits log-log regression and predicts time at next_n."""
    points = [
        (r["n"], r["ms"]) for r in partial_results
        if r.get("ms") is not None and r.get("ok") and r["ms"] > 1e-7
    ]
    if len(points) < 2:
        return None
    log_ns = [math.log2(p[0]) for p in points]
    log_ms = [math.log2(p[1]) for p in points]
    n_pts = len(points)
    mean_x = sum(log_ns) / n_pts
    mean_y = sum(log_ms) / n_pts
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(log_ns, log_ms))
    den = sum((x - mean_x) ** 2 for x in log_ns)
    if den < 1e-10:
        return None
    slope = num / den
    intercept = mean_y - slope * mean_x
    predicted_ms = 2 ** (slope * math.log2(next_n) + intercept)
    return {"predicted_ms": round(predicted_ms, 1), "will_timeout": predicted_ms > 8000}


# ── Code similarity (character n-gram Jaccard) ────────────────────────────────

def code_similarity(code_a: str, code_b: str) -> float:
    """
    Returns Jaccard similarity [0, 1] between two code submissions using
    character 5-grams on normalized (whitespace-stripped, lowercased) code.
    """
    def _normalize(code: str) -> str:
        return re.sub(r'\s+', '', code.lower())

    def _ngrams(s: str, n: int = 5) -> set:
        return {s[i:i+n] for i in range(len(s) - n + 1)}

    a = _normalize(code_a)
    b = _normalize(code_b)
    if not a or not b:
        return 0.0
    ng_a = _ngrams(a)
    ng_b = _ngrams(b)
    union = len(ng_a | ng_b)
    if union == 0:
        return 1.0
    return round(len(ng_a & ng_b) / union, 3)


# ── ELO skill tracker ─────────────────────────────────────────────────────────

class EloTracker:
    """
    Tracks player skill and problem difficulty using ELO.
    Player wins (solves problem) → skill up, difficulty down slightly.
    Player loses (timeout/error) → skill down, difficulty up slightly.
    """
    K = 32
    DEFAULT = 1000
    _INITIAL_DIFFICULTIES = {
        "two_sum":      1000,
        "max_subarray": 1100,
        "bubble_sort":   950,
    }
    _TIERS = [(1200, "Expert"), (1100, "Advanced"), (1000, "Intermediate"), (0, "Beginner")]

    def __init__(self):
        self._skills: dict = {}
        self._difficulties: dict = dict(self._INITIAL_DIFFICULTIES)
        # Keyed by player name. Distinct from _attempts, which is keyed by
        # problem — conflating the two made the difficulty blend below a
        # no-op, since a problem id is never a key in here.
        self._solve_counts: dict = defaultdict(int)
        self._attempts: dict = defaultdict(int)     # problem_id -> times rated

    def get_skill(self, name: str) -> float:
        return self._skills.get(name, self.DEFAULT)

    def get_difficulty(self, problem_id: str) -> float:
        return self._difficulties.get(problem_id, self.DEFAULT)

    def get_attempts(self, problem_id: str) -> int:
        """How many rated attempts a problem has seen — the confidence behind
        its ELO difficulty."""
        return self._attempts[problem_id]

    def tier(self, name: str) -> str:
        s = self.get_skill(name)
        for threshold, label in self._TIERS:
            if s >= threshold:
                return label
        return "Beginner"

    def update(self, name: str, problem_id: str, solved: bool) -> float:
        """Update ratings; return the ELO delta for the player."""
        S = self.get_skill(name)
        D = self.get_difficulty(problem_id)
        expected = 1 / (1 + 10 ** ((D - S) / 400))
        outcome = 1.0 if solved else 0.0
        delta = self.K * (outcome - expected)
        self._skills[name] = S + delta
        self._difficulties[problem_id] = D + self.K * (expected - outcome)
        self._attempts[problem_id] += 1
        if solved:
            self._solve_counts[name] += 1
        return round(delta)

    def recommend(self, name: str, problem_ids: list) -> str:
        """Return the problem whose difficulty is closest to the player's skill."""
        skill = self.get_skill(name)
        return min(problem_ids, key=lambda pid: abs(self.get_difficulty(pid) - skill))

    def leaderboard(self) -> list:
        return sorted(
            [{"name": n, "skill": round(s), "tier": self.tier(n),
              "solves": self._solve_counts[n]}
             for n, s in self._skills.items()],
            key=lambda x: x["skill"], reverse=True
        )


# ── Solve time tracker (log-normal distribution) ──────────────────────────────

class SolveTimeTracker:
    """
    Records how long each player takes to solve each problem (ms from room join
    to submission) and models the distribution as log-normal to compute
    per-solve speed percentiles.
    """
    def __init__(self):
        self._times: dict = defaultdict(list)  # problem_id -> [ms]

    def percentile(self, problem_id: str, time_ms: float) -> int:
        """Percentage of past solves that were SLOWER than this one (higher = faster)."""
        past = self._times[problem_id]
        if not past:
            return None
        slower = sum(1 for t in past if t > time_ms)
        return round(slower / len(past) * 100)

    def add(self, problem_id: str, time_ms: float):
        self._times[problem_id].append(time_ms)

    def stats(self, problem_id: str) -> dict:
        times = self._times[problem_id]
        if len(times) < 2:
            return None
        log_t = [math.log(t) for t in times if t > 0]
        mu = sum(log_t) / len(log_t)
        sigma = math.sqrt(sum((x - mu) ** 2 for x in log_t) / len(log_t))
        median_ms = round(math.exp(mu))
        return {"count": len(times), "median_ms": median_ms,
                "mu": round(mu, 3), "sigma": round(sigma, 3)}


# ── Problem difficulty estimator (text features) ──────────────────────────────

class DifficultyEstimator:
    """
    Estimates problem difficulty (1–10) from its description text using
    weighted keyword/structural features. Blends with ELO-derived difficulty
    once enough solve data exists.
    """
    _HARD_SIGNALS = {
        'optimal', 'without', 'exactly', 'distinct', 'unique', 'duplicates',
        'matrix', 'tree', 'graph', 'linked', 'heap', 'queue', 'stack',
        'substring', 'subsequence', 'permutation', 'combination',
    }
    _MEDIUM_SIGNALS = {
        'indices', 'index', 'subarray', 'maximum', 'minimum', 'consecutive',
        'target', 'pair', 'sorted',
    }

    def score(self, description: str, problem_id: str = None,
              elo: "EloTracker" = None) -> dict:
        words = set(description.lower().split())
        hard_hits = len(words & self._HARD_SIGNALS)
        medium_hits = len(words & self._MEDIUM_SIGNALS)
        word_count = len(description.split())

        raw = (
            hard_hits * 2.0 +
            medium_hits * 0.8 +
            min(word_count / 20, 2.0)
        )
        text_score = min(10, max(1, round(raw + 3)))

        # Blend with ELO difficulty once we have data
        final_score = text_score
        if elo and problem_id:
            elo_diff = elo.get_difficulty(problem_id)
            # ELO starts at 1000; map [800, 1300] → [1, 10]
            elo_score = round((elo_diff - 800) / 50 + 1)
            elo_score = min(10, max(1, elo_score))
            # Attempts on this problem, not solves by some player of the same
            # name: _solve_counts is keyed by player, so the old lookup was
            # always 0 and the ELO term never carried any weight at all.
            attempts = elo.get_attempts(problem_id)
            weight = min(attempts / 20, 0.8)  # ELO reaches 80% weight at 20 attempts
            final_score = round(weight * elo_score + (1 - weight) * text_score)

        tier = "Hard" if final_score >= 7 else ("Medium" if final_score >= 4 else "Easy")
        return {"score": final_score, "tier": tier}


# ── Module-level singletons (imported by benchmarks, rooms, routes) ───────────

clusterer = SolutionClusterer()
elo = EloTracker()
solve_times = SolveTimeTracker()
difficulty = DifficultyEstimator()
