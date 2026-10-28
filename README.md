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

## Tile countdown and end of game

- The complete requested 144-tile Bananagrams distribution is still used at the start of every game.
- The **tiles left** counter starts at 144 and decreases every time center letters are claimed or used to extend/steal words. Claimed tiles disappear from the scattered pile. Flipping alone reveals a tile but does not remove it.
- Once **all 144 tiles have been used** (no face-down or revealed center tiles left), the game ends automatically. The server blocks further flips and word submissions and announces the winner(s) by total letters across their owned words, including ties.
- If all tiles have been revealed but some remaining letters cannot form any valid word, the game will not automatically finish; they still count as tiles left.

To deploy: replace **app.py** and **static/index.html** in your existing GitHub repository, commit, then deploy the latest commit on Render. Keep the existing `static/boom.jpg` and `static/steal.jpg` files. Create a fresh room after deployment.


## Winner announcement
When all center tiles are used, every player sees `static/winner.jpg` with a flashing WINNER message, the winner’s name, and final letter score. Ties display all tied names. The announcement can be closed.

## New winner criteria and comic-style celebration

The winner is now the player owning the **most words** when all 144 tiles have been used; word lengths do not count. Stealing moves the word to the thief, and extending your own word still counts as one word. Ties are announced together. The comic-style WINNER image matches the BOOM/SUCK IT graphics. The player's actual name is shown on a dynamic banner (the image has no hard-coded player name).

To update the live site, replace `app.py`, `static/index.html`, and `static/winner.jpg` on GitHub. Render will redeploy on commit or use Manual Deploy → Deploy latest commit. New rooms are required.


## Blue + yellow theme update
The complete interface now uses navy/royal-blue panels and backgrounds, gold/yellow buttons and highlights, blue tile backs, and pale-yellow face-up tiles. All game logic and image files are preserved. Update `static/index.html` in your existing GitHub repository, commit, then deploy the latest commit on Render.
