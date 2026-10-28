# Word Steal Online

Two-player, live online word game. One player creates a room and shares the six-character code or URL. Both players race to claim words from the same revealed center tiles. The first *valid claim to arrive at the server* wins.

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

Important: use **one server worker / one instance**, because rooms exist in server memory. Deployments and instance restarts erase rooms. Free hosting can sleep between sessions. This prototype does not yet offer reconnection or durable rooms; a disconnected player's seat remains reserved until the server restarts.

## Rules

- 144 tiles with standard Bananagrams letter counts.
- Flip turns alternate; any player may submit a word at any time once both players have joined.
- Claim a valid word of 3+ letters using only center tiles; claimed letters are removed from the center.
- To steal, select an opponent's word, then submit a different valid word that uses every letter of that word plus at least one letter currently available in the center. The existing word moves to the stealing player.
- Basic plural and inflection-only additions (`CAT→CATS`, `PLAY→PLAYED`, `RUN→RUNNING`, `CITY→CITIES`) are blocked by heuristics. Exception and irregular-form handling is not comprehensive.
- Validation uses `wordfreq` frequency data as a lightweight English word validator. It is not a tournament dictionary and may accept proper names, inflections and uncommon forms. You can replace `valid_word` with a curated dictionary.

## Production limitations

Prototype only: no accounts, moderation, per-room persistence, reconnection, or rate limiting; room codes are guessable; scalable deployment requires shared storage/message coordination. Rooms are not listed publicly but room codes are not secure authentication. Suitable for casual friendly games.
