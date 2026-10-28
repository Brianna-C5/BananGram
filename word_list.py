"""ENABLE word list: local, offline validation for every claim.
ENABLE (public domain, ~173k words) contains no proper nouns, so names of
people, places and brands are rejected without any API call.
"""
from pathlib import Path

_WORDS = frozenset((Path(__file__).resolve().parent/'enable1.txt').read_text().split())

def is_valid_word(word):
    return word.lower() in _WORDS
