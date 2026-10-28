# Word Steal Online — compact screen + automatic steals

Browser-based multiplayer word game with a Python FastAPI server and WebSocket updates.

## Current rules

- Up to eight people can join a room with a six-character code. A room starts with the specified 144 Bananagrams letter tiles, face-down in a scattered pile.
- The player whose turn it is flips one tile; flipping normally advances the turn to the next connected player.
- Any connected player can race to submit a word at any time, regardless of whose turn it is.
- The server validates American-English-focused words (3+ letters) and checks every player’s existing words automatically, including your own. No word selection is necessary.
- When a word can extend a previously claimed word with at least one extra center tile, the eligible existing word is consumed. If it belonged to someone else, the new word goes to the claiming player; if it was yours, it remains yours. With multiple matches, the server prefers the longest base word, then another player's word, then the oldest ID.
- If no eligible extension exists, a word can be made entirely from the center letters.
- Simple plural/tense-only extensions such as CAT→CATS, PLAY→PLAYED, RUN→RUNNING are blocked. Valid rearrangements such as CAT→REACT remain allowed. The rule covers common spelling patterns, not all irregular inflections.
- Every revealed center tile used for the claim disappears from the scattered board and the visible center letters count decreases. Unrevealed tiles remain face-down and can be flipped later.
- Whoever successfully claims or steals a word gains the next flip, overriding the normal next player. After that flip, turns continue in seat order unless another word is claimed.
- The board is on the left; word entry and up to eight player piles are on the right in a condensed desktop view. Small screens use a responsive stacked view and may require scrolling.

## Deploy an update to an existing Render website

1. Unzip the archive.
2. In your existing GitHub repository, replace the root `app.py` with this one and replace `static/index.html` with this version.
3. Keep `american_english.py`, `requirements.txt`, and `render.yaml` at the root, plus the `static` directory containing `index.html`.
4. Commit both changes. Render should automatically deploy; otherwise choose **Manual Deploy → Deploy latest commit** for your existing service.
5. Once Render reports **Live**, hard refresh the website and create a **new room**. In-memory rooms don't survive a restart.

Do not upload the ZIP as a single file to GitHub; upload its extracted contents.

## Run locally

```bash
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

Visit http://127.0.0.1:8000 . For play on different devices, deploy the app to a host that supports WebSockets.

## Known limitations

- Rooms live in one Python server process and disappear when the server restarts; the Render configuration uses one worker. No database, reconnect seat recovery, or cross-instance synchronization.
- Word validation is American-English-focused, not a licensed tournament dictionary. The morphology filter is heuristic.
- No live browser test across eight devices has been performed.


### Banana celebrations
Every successful newly claimed center word (or extension of your own word) triggers a banana BOOM animation. Stealing another player's word triggers a smirking banana SUCK IT animation. The server broadcasts a unique effect ID to the entire room so all connected players see the celebration once. The overlay does not intercept clicks.

Update **both** `app.py` and `static/index.html` on GitHub, then redeploy on Render.

### Custom celebration images
The generated images are saved as `static/boom.jpg` (new center word or extending your own word) and `static/steal.jpg` (stealing someone else's word). The existing server sends the effect event to everyone in the room. The images display briefly and do not block gameplay.

To update an existing deployment, upload **three files** to the same paths in GitHub: `static/index.html`, `static/boom.jpg`, and `static/steal.jpg`. If the existing deployed server is older than the banana-effects update, also replace root `app.py` from this package. Commit and redeploy on Render.
