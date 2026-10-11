"""Cheap text-similarity used to keep episodes from collapsing into one template."""
import re

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_ALEF = re.compile(r"[آأإ]")


def tokens(text: str) -> list[str]:
    text = _TASHKEEL.sub("", text.lower())
    text = _ALEF.sub("ا", text).replace("ى", "ي").replace("ة", "ه")
    return re.findall(r"\w+", text)


def shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    toks = tokens(text)
    if len(toks) < n:
        return {tuple(toks)} if toks else set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def jaccard(a: str, b: str, n: int = 3) -> float:
    sa, sb = shingles(a, n), shingles(b, n)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def max_similarity(text: str, others: list[str], n: int = 3) -> tuple[float, int]:
    """(best score, index of the most similar text) against a history."""
    best, idx = 0.0, -1
    for i, other in enumerate(others):
        s = jaccard(text, other, n)
        if s > best:
            best, idx = s, i
    return best, idx


def opening(text: str, words: int) -> str:
    return " ".join(tokens(text)[:words])
