"""ENABLE word list: local, offline validation for every claim.
ENABLE (public domain, ~173k words) contains no proper nouns, so names of
people, places and brands are rejected without any API call.
"""
from collections import Counter, defaultdict
from pathlib import Path

_WORDS = frozenset((Path(__file__).resolve().parent/'enable1.txt').read_text().split())

def _mask(letters):
    return sum(1 << (ord(c)-97) for c in set(letters))

# Grouped by length with letter bitmasks so "what can these letters spell" scans stay fast.
_BY_LEN = defaultdict(list)
for _w in _WORDS:
    _BY_LEN[len(_w)].append((_mask(_w), _w))

def is_valid_word(word):
    return word.lower() in _WORDS

def words_from(letters, min_len=3):
    '''Yield upper-case dictionary words spellable from the multiset `letters`.'''
    pool = Counter(letters.lower())
    missing = ((1 << 26)-1) ^ _mask(pool)
    for n in range(min_len, sum(pool.values())+1):
        for m, w in _BY_LEN.get(n, ()):
            if not m & missing and not Counter(w)-pool:
                yield w.upper()
