# Word Steal Online

Two-to-eight-player, live online word game. One player creates a room and shares the six-character code or URL. All connected players race to claim words from the same revealed center tiles. The first *valid claim to arrive at the server* wins.

## Run locally

Install Python 3.10+ then from this directory:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Open http://localhost:8000 and create a room. To test on a second browser tab or device on the same network, open the same server address.

## Get a public link (Render)

1. Create a new GitHub repository and upload `app.py`, `requirements.txt`, `render.yaml`, and `static/index.html` (preserve the folder structure).
2. Go to https://dashboard.render.com/ and choose **New > Blueprint**. Connect your GitHub repository; Render detects `render.yaml`.
3. Deploy the service. Render will show your public URL, typically `https://word-steal-online-xxxx.onrender.com` (actual URL is assigned by Render).
4. Visit that URL. Click **Create a room**, then **Copy invite link** to send to a friend. Friends may also enter your six-character code.

Important: use **one server worker / one instance**, because rooms exist in server memory. Deployments and instance restarts erase rooms. Free hosting can sleep between sessions. This prototype does not yet offer reconnection or durable rooms; a disconnected player's seat remains reserved until the server restarts, although turns skip disconnected players.

## Updated board and room rules

- The lobby previews **all 144 face-down tiles**; the room displays the same 144 tiles in a 12×12 grid.
- When it is your turn, click any face-down tile. Its letter stays visible where it was flipped, and that letter is added to the available center pool.
- A room admits **2–8 players** with the same six-character invitation code; only a single creator is required to open the room.
- Turns rotate through connected players; word claims can be submitted by anyone at any time once at least two players have joined.

## Rules

- 144 tiles with standard Bananagrams letter counts.
- Flip turns rotate among connected players; any player may submit a word at any time once both players have joined.
- Claim a valid word of 3+ letters using only center tiles; claimed letters are removed from the center.
- Select **any existing word**, including one you own. Submit a different valid word that uses **every letter of the selected word** plus **at least one letter from the center**. If the word belongs to another player, it is stolen and moved to your pile. If it is already yours, your word is extended in your own pile. Both actions consume only the newly added center letters.
- Simple plurals or verb-tense changes do not count as valid extensions or steals, even for your own word.
- Basic plural and inflection-only additions (`CAT→CATS`, `PLAY→PLAYED`, `RUN→RUNNING`, `CITY→CITIES`) are blocked by heuristics. Exception and irregular-form handling is not comprehensive.
- Validation now uses an American-pronunciation lexicon (`cmudict`), an English frequency threshold (`wordfreq`), and a list of British-specific spellings to reject common UK variants (e.g. COLOUR, CENTRE, REALISE). This is an American-English-focused casual-game dictionary, **not an official US tournament dictionary**. Some regional spellings, proper nouns, abbreviations, and rare words may still be imperfectly classified.

## Production limitations

Prototype only: no accounts, moderation, per-room persistence, reconnection, or rate limiting; room codes are guessable; scalable deployment requires shared storage/message coordination. Rooms are not listed publicly but room codes are not secure authentication. Suitable for casual friendly games.

## Updating an existing Render website

Upload the updated `app.py`, `README.md`, and `static/index.html` to the **same paths** in the existing GitHub repository, replacing old versions. Do not upload the ZIP itself. Render usually auto-deploys commits; otherwise choose **Manual Deploy → Deploy latest commit** on the web service. After deployment, refresh the page and **create a new room** (existing server-memory rooms are lost upon deployment).

## American English dictionary update

New file: `american_english.py`. In GitHub, place it **beside `app.py`** (not inside `static`) and replace the existing `app.py` and `requirements.txt`. The original 144-tile board, 8-player capacity, and word-stealing rules are unchanged. Render must install the new `cmudict` dependency.

## Updating to the extend-your-own-words version

In the existing GitHub repository, replace `app.py`, `static/index.html`, and `README.md` with the corresponding files from this download. Keep the existing `american_english.py`, `requirements.txt`, and `render.yaml`. Commit the changes; Render should auto-deploy. Create a new room after deployment.

## Scattered 144-tile board

The lobby preview and live board now show all 144 tiles in a stable, loosely scattered pile (not a 12×12 grid). The tile positions are deterministic on every device. Click any face-down tile on your turn; the server still controls the identity of each revealed letter.
