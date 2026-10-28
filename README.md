# Word Steal Online — Merriam-Webster update

## What's new
- A blue-and-yellow **Latest Word** definition panel under the player-name header, synchronized to all devices.
- Words are validated locally against the **ENABLE** word list (`enable1.txt`, public domain, ~173k words). No API key or network is needed to play.
- ENABLE contains no proper nouns, so person names, place names, named products and brands are rejected. Common nouns (e.g. TABLE) remain legal.
- Definitions for the Latest Word panel come from the Merriam-Webster API when a key is configured; otherwise the panel shows "Definition unavailable".
- Existing rules, 144 tiles, eight players, animations and most-words-wins scoring are preserved.

## OPTIONAL: Merriam-Webster definitions
1. Register at https://dictionaryapi.com/ and obtain a **Collegiate Dictionary** API key (not a Thesaurus API key).
2. In Render, choose your web service → Environment → add environment variable `MERRIAM_WEBSTER_API_KEY` with your secret API key.
3. Save and redeploy. Never put this key in GitHub, HTML or client code.
4. Replace `app.py`, `requirements.txt`, `static/index.html` in GitHub; add `merriam_webster.py` at repository root. Keep existing `render.yaml` and image files, or upload the entire extracted package.

**Terms/limits:** Merriam-Webster's free noncommercial API allows up to 1,000 queries/day per reference. API terms and current branding requirements apply. See https://dictionaryapi.com/info/terms-of-service and https://dictionaryapi.com/info/frequently-asked-questions . This project provides a Merriam-Webster link/attribution; review their current logo requirements before publishing widely.

## Rejoining after a disconnect
A player who disconnects can return through **Join / Rejoin with code**, entering the original six-character room code and **the same nickname** (case-insensitive). Their existing seat, words, and score are restored, even when all eight seats have been taken. Names must be unique within each room; an already-connected seat cannot be taken over. The turn passes to a connected player when someone disconnects.

**Security:** A room code plus nickname is not identity verification. Someone who knows both can claim an *offline* seat. For private games with stronger security, add a persistent per-player secret rejoin token or user authentication. Rooms are held in server memory and are lost when Render restarts or the process sleeps.
