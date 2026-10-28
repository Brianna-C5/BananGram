"""Merriam-Webster Collegiate API: optional definitions for the Latest Word panel.
Word validity comes from word_list.py; this returns None when no key is set or MW fails.
Configure MERRIAM_WEBSTER_API_KEY as a Render environment secret.
"""
import asyncio
import os
import re
from collections import OrderedDict
import httpx

API_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json/"
_CACHE = OrderedDict()
_LOCK = asyncio.Lock()
MAX_CACHE = 5000
BAD_LABELS = ("chiefly british", "chiefly brit", "british spelling", "british variant", "chiefly canadian")
PROPER_PARTS = ("biographical name", "geographical name", "proper noun", "trademark")

def _clean(text):
    # Remove MW inline formatting instructions such as {bc}, {it} and {d_link|...}.
    text=re.sub(r"\{[^{}]*\|([^{}|]*)\}",r"\1",text)
    text=re.sub(r"\{/?[^{}]*\}","",text)
    return re.sub(r"\s+", " ", text).strip(" :;.,")[:220]

def _entry_for(word, data):
    if not isinstance(data, list): return None
    candidates=[]
    for ent in data:
        if not isinstance(ent,dict): continue
        meta=ent.get('meta') or {}
        head=str(meta.get('id','')).split(':')[0]
        stems=meta.get('stems') or []
        # Require exact spelling or a documented inflected form, never mere suggestions.
        if word != head.lower() and word not in {str(x).lower() for x in stems}:continue
        fl=str(ent.get('fl','')).lower()
        if any(part in fl for part in PROPER_PARTS): continue
        # Exclude headwords that are only proper names. Exact lower-case common-word entries remain valid.
        raw_head=str(ent.get('hwi',{}).get('hw','')).replace('*','')
        if raw_head and raw_head[0].isupper() and raw_head.lower()==word:continue
        labels=' '.join(str(ent.get(k,'')) for k in ('lbs','sl','vl')).lower()
        if any(bad in labels for bad in BAD_LABELS): continue
        short=ent.get('shortdef') or []
        if not short:continue
        definition=_clean(str(short[0]))
        if definition: candidates.append({'definition':definition,'partOfSpeech':ent.get('fl','word')})
    return candidates[0] if candidates else None

async def lookup_word(word):
    word=word.lower().strip()
    if not word.isascii() or not word.isalpha():return None
    key=os.environ.get('MERRIAM_WEBSTER_API_KEY','').strip()
    if not key:return None  # No silent fallback to a different dictionary.
    cache_key=(key,word)
    if cache_key in _CACHE:
        _CACHE.move_to_end(cache_key)
        return _CACHE[cache_key]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r=await client.get(API_URL+word,params={'key':key})
            r.raise_for_status()
            result=_entry_for(word,r.json())
    except (httpx.HTTPError, ValueError):
        return None  # Fail closed; don't cache network failures.
    _CACHE[cache_key]=result
    if len(_CACHE)>MAX_CACHE:_CACHE.popitem(last=False)
    return result
