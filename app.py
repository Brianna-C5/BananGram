import asyncio
import json
import random
import secrets
import string
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from merriam_webster import lookup_word
from word_list import is_valid_word, words_from

app = FastAPI()
ROOT = Path(__file__).resolve().parent
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')

# Original Bananagrams 144-tile English distribution.
TILE_COUNTS = {'A':13,'B':3,'C':3,'D':6,'E':18,'F':3,'G':4,'H':3,'I':12,'J':2,'K':2,'L':5,'M':3,'N':8,'O':11,'P':3,'Q':2,'R':9,'S':6,'T':9,'U':6,'V':3,'W':3,'X':2,'Y':3,'Z':2}
assert sum(TILE_COUNTS.values()) == 144
# Scrabble-style letter values; a word is worth the sum of its letters.
LETTER_VALUES = {'A':1,'B':3,'C':3,'D':2,'E':1,'F':4,'G':2,'H':4,'I':1,'J':8,'K':5,'L':1,'M':3,'N':1,'O':1,'P':3,'Q':10,'R':1,'S':1,'T':1,'U':1,'V':4,'W':4,'X':8,'Y':4,'Z':10}
ROOMS = {}
MAX_PLAYERS = 8
# Host-adjustable flip clock, in seconds.
TURN_SECONDS_MIN, TURN_SECONDS_MAX, TURN_SECONDS_STEP = 15, 90, 5

@dataclass
class Room:
    code: str
    bag: list = field(default_factory=list)
    center: Counter = field(default_factory=Counter)
    words: list = field(default_factory=list)
    names: list = field(default_factory=list)
    sockets: list = field(default_factory=list)
    turn: int = 0
    message: str = 'Invite up to 7 friends with the room code!'
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    seq: int = 0
    revealed: set = field(default_factory=set)
    used: set = field(default_factory=set)
    last_effect: Optional[dict] = None
    finished: bool = False
    winners: list = field(default_factory=list)
    winning_score: int = 0
    latest_word: Optional[dict] = None
    started: bool = False
    turn_seconds: int = TURN_SECONDS_MIN
    turn_token: int = 0  # Bumped on every new turn so a stale timer knows not to fire.
    turn_deadline: Optional[float] = None  # time.monotonic() when the turn clock runs out.
    timer: Optional[asyncio.Task] = None
    end_votes: set = field(default_factory=set)

    def host(self):
        '''The first connected player may press Play, so an offline creator cannot stall the room.'''
        return next((i for i, ws in enumerate(self.sockets) if ws is not None), 0)

    def scores(self):
        return [sum(e['points'] for e in self.words if e['owner']==i) for i in range(len(self.names))]

    def votes_needed(self):
        '''A strict majority of the players currently online.'''
        return sum(ws is not None for ws in self.sockets)//2+1

    def live_votes(self):
        return sorted(i for i in self.end_votes if self.sockets[i] is not None)

    def board_public(self):
        return ['USED' if idx in self.used else letter if idx in self.revealed else None for idx, letter in enumerate(self.bag)]

    def public(self):
        active_tiles = len(self.bag) - len(self.used)
        return {'type':'state','code':self.code,'remaining':len(self.bag)-len(self.revealed),'tilesLeft':active_tiles,'finished':self.finished,'center':dict(self.center),
                'words':self.words,'board':[letter if letter is not None else None for letter in self.board_public()], 'maxPlayers':MAX_PLAYERS,'players':[{'name':n,'connected':self.sockets[i] is not None} for i,n in enumerate(self.names)],
                'turn':self.turn,'message':self.message,'usedCount':len(self.used),
                'effect':self.last_effect,'winners':self.winners,'winningScore':self.winning_score, 'latestWord':self.latest_word,
                'started':self.started,'host':self.host(),'turnSeconds':self.turn_seconds,'turnSecondsRange':[TURN_SECONDS_MIN,TURN_SECONDS_MAX,TURN_SECONDS_STEP],
                'turnEndsIn':None if self.turn_deadline is None else max(0.0,self.turn_deadline-time.monotonic()),'scores':self.scores(),'letterValues':LETTER_VALUES,
                'endVotes':self.live_votes(),'endVotesNeeded':self.votes_needed()}


def new_room():
    alphabet = [letter for letter,count in TILE_COUNTS.items() for _ in range(count)]
    random.SystemRandom().shuffle(alphabet)
    while True:
        code = ''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6))
        if code not in ROOMS: break
    room = Room(code=code,bag=alphabet)
    ROOMS[code] = room
    return room


def valid_word(word):
    return len(word) >= 3 and word.isascii() and word.isalpha() and is_valid_word(word)


def invalid_extension(old,new):
    '''Block common plural and verb-inflection-only extensions; other meaningful anagrams are allowed.'''
    o,n = old.lower(),new.lower()
    if n in {o+'s',o+'es',o+'ed',o+'d',o+'ing',o+'er',o+'est'}: return True
    if o.endswith('y') and n in {o[:-1]+'ies',o[:-1]+'ied'}: return True
    if o.endswith('e') and n in {o[:-1]+'ing',o+'d'}: return True
    if len(o)>2 and o[-1] not in 'aeiou' and n in {o+o[-1]+'ed',o+o[-1]+'ing'}: return True
    if n in {o+'en',o+'n'}: return True
    return False


def word_points(word):
    return sum(LETTER_VALUES[c] for c in word)


def claim_possible(center, pile_words):
    '''True if any legal claim remains: a new word from the center, or an extension/steal of a pile word.'''
    if not center: return False  # Every claim consumes at least one center letter.
    letters=''.join(center.elements())
    if next(words_from(letters), None): return True
    for old in set(pile_words):
        need=Counter(old)
        for word in words_from(letters+old, len(old)+1):
            if not need-Counter(word) and not invalid_extension(old,word): return True
    return False


def end_game(room, reason):
    room.finished=True
    start_turn_timer(room)  # Stops the clock now that the game is finished.
    scores=room.scores()
    best=max(scores) if scores else 0
    room.winners=[room.names[i] for i,score in enumerate(scores) if score==best]
    room.winning_score=best
    room.message=f'GAME OVER! {reason} Winner: {", ".join(room.winners)} ({best} points)!'


async def check_game_over(room):
    '''Once every tile is face-up, end the game when no claim can be made with what is left.'''
    if room.finished or len(room.revealed) < len(room.bag): return
    if await asyncio.to_thread(claim_possible, Counter(room.center), [e['word'] for e in room.words]): return
    end_game(room,'All letters are off the board.' if not room.center else 'No more words can be made from the remaining letters.')


def check_end_vote(room):
    '''End the game as soon as a majority of the players online have voted to.'''
    votes=room.live_votes()
    if not room.finished and votes and len(votes) >= room.votes_needed():
        end_game(room,'Players voted to end the game.')


def start_turn_timer(room):
    '''(Re)start the turn clock for room.turn; it stays off before Play, after the game and while nobody is online.'''
    room.turn_token+=1
    room.turn_deadline=None
    if room.timer is not None and room.timer is not asyncio.current_task():
        room.timer.cancel()
    room.timer=None
    if not room.started or room.finished or not any(room.sockets):
        return
    room.turn_deadline=time.monotonic()+room.turn_seconds
    room.timer=asyncio.create_task(turn_timeout(room,room.turn_token,room.turn_seconds))


async def turn_timeout(room, token, seconds):
    '''When the clock runs out, flip a random face-down tile for the turn player, or just pass once none are left.'''
    await asyncio.sleep(seconds)
    async with room.lock:
        if token!=room.turn_token: return
        face_down=[i for i in range(len(room.bag)) if i not in room.revealed]
        if face_down:
            await flip_tile(room,random.choice(face_down),auto=True)
        else:
            idle=room.names[room.turn]
            pass_turn(room)
            room.message=f"Time's up, {idle}! No tiles left to flip, so it's {room.names[room.turn]}'s turn."
            start_turn_timer(room)
        await broadcast(room)


def pass_turn(room):
    '''Move the turn to the next connected player.'''
    room.turn=(room.turn+1)%len(room.names)
    for _ in range(len(room.names)):
        if room.sockets[room.turn] is not None: break
        room.turn=(room.turn+1)%len(room.names)


async def flip_tile(room, tile, auto=False):
    '''Reveal one tile, pass the flip to the next connected player and restart the clock.'''
    flipper=room.names[room.turn]
    letter=room.bag[tile]
    room.revealed.add(tile)
    room.center[letter]+=1
    pass_turn(room)
    room.message=(f"Time's up, {flipper}! A random tile was flipped: {letter}." if auto else
                  f'{flipper} revealed {letter}. Everyone can race to claim words!')
    start_turn_timer(room)
    await check_game_over(room)


async def broadcast(room):
    state=room.public()
    for ws in room.sockets:
        if ws is not None:
            try: await ws.send_json(state)
            except Exception: pass

async def error(ws, msg):
    await ws.send_json({'type':'error','message':msg})

@app.get('/')
def homepage(): return FileResponse(ROOT/'static'/'index.html')

@app.get('/health')
def health(): return {'ok':True}

@app.websocket('/ws')
async def connect(ws: WebSocket):
    await ws.accept()
    room: Optional[Room] = None
    seat: Optional[int] = None
    try:
        while True:
            data=await ws.receive_json()
            action=data.get('action')
            if room is None:
                if action not in ('create','join'):
                    await error(ws,'Create or join a room first.');continue
                code=str(data.get('code','')).strip().upper()
                name=str(data.get('name','Player')).strip()[:20] or 'Player'
                if action=='create':
                    room=new_room()
                else:
                    room=ROOMS.get(code)
                    if room is None:
                        await error(ws,'Room not found. Check the code.'); continue
                async with room.lock:
                    # A nickname uniquely identifies a seat within a room. Rejoining
                    # restores that seat instead of creating a new player or score.
                    existing = next((i for i, n in enumerate(room.names)
                                     if n.casefold() == name.casefold()), None)
                    if action == 'create':
                        existing = None
                    if existing is not None:
                        if room.sockets[existing] is not None:
                            await error(ws, 'That name is already connected. If this is your seat, disconnect the old device first.')
                            room = None
                            continue
                        seat = existing
                        room.sockets[seat] = ws
                        name = room.names[seat]  # Preserve original spelling.
                        room.message = f'{name} rejoined the game!'
                        # Ensure a connected player gets the next flip when the
                        # previously designated turn-holder is offline.
                        if room.sockets[room.turn] is None:
                            room.turn = seat
                            start_turn_timer(room)
                        elif room.turn_deadline is None:
                            start_turn_timer(room)  # Resume a clock paused while everyone was offline.
                        await ws.send_json({'type': 'welcome', 'seat': seat, 'code': room.code, 'rejoined': True})
                        await broadcast(room)
                    else:
                        if action == 'join' and len(room.names) >= MAX_PLAYERS:
                            await error(ws, 'This room already has eight players. Rejoin using the exact name of an offline player.')
                            room = None
                            continue
                        seat = len(room.names)
                        room.names.append(name)
                        room.sockets.append(ws)
                        room.message = f'{name} joined! ' + ('' if room.started else f'{len(room.names)} players ready. {room.names[room.host()]} can press Play to start!' if len(room.names)>=2 else 'Waiting for another player.')
                        await ws.send_json({'type':'welcome','seat':seat,'code':room.code, 'rejoined': False})
                        await broadcast(room)
                continue
            async with room.lock:
                if room.finished and action in ('flip', 'claim', 'start', 'vote_end', 'settings'):
                    await error(ws, 'Game over! Create a new room to play again.'); continue
                if not room.started and action in ('flip', 'claim', 'vote_end'):
                    await error(ws, f'Waiting for {room.names[room.host()]} to press Play.'); continue
                if action=='settings':
                    if room.started:
                        await error(ws,'Settings are locked once the game starts.');continue
                    if seat != room.host():
                        await error(ws,f'Only {room.names[room.host()]} can change settings.');continue
                    try: seconds=int(data.get('turnSeconds'))
                    except (ValueError,TypeError):
                        await error(ws,'Choose a turn length.');continue
                    seconds=round(seconds/TURN_SECONDS_STEP)*TURN_SECONDS_STEP
                    room.turn_seconds=min(TURN_SECONDS_MAX,max(TURN_SECONDS_MIN,seconds))
                    room.message=f'{room.names[seat]} set each turn to {room.turn_seconds} seconds.'
                    await broadcast(room)
                elif action=='start':
                    if room.started:
                        await error(ws,'The game has already started.');continue
                    if len(room.names)<2:
                        await error(ws,'Wait for a second player to join.');continue
                    if seat != room.host():
                        await error(ws,f'Only {room.names[room.host()]} can start the game.');continue
                    room.started=True
                    room.turn=seat
                    room.message=f'{room.names[seat]} started the game and flips first!'
                    start_turn_timer(room)
                    await broadcast(room)
                elif action=='vote_end':
                    if len(room.revealed)<len(room.bag):
                        await error(ws,'You can vote to end once every tile is face-up.');continue
                    room.end_votes^={seat}  # Pressing again takes the vote back.
                    voted=seat in room.end_votes
                    room.message=(f'{room.names[seat]} {"voted to end the game" if voted else "took back their vote"} '
                                  f'({len(room.live_votes())}/{room.votes_needed()} needed).')
                    check_end_vote(room)
                    await broadcast(room)
                elif action=='flip':
                    if len(room.names)<2:
                        await error(ws,'Wait for a second player to join.');continue
                    if seat != room.turn:
                        await error(ws,'It is not your turn to flip.');continue
                    if len(room.revealed)==len(room.bag):
                        await error(ws,'All tiles have been revealed.');continue
                    try: tile=int(data.get('index'))
                    except (ValueError,TypeError):
                        await error(ws,'Choose a tile to flip.');continue
                    if tile<0 or tile>=len(room.bag) or tile in room.revealed:
                        await error(ws,'That tile is already revealed or does not exist.');continue
                    await flip_tile(room,tile)
                    await broadcast(room)
                elif action=='claim':
                    if len(room.names)<2:
                        await error(ws,'Wait for a second player to join.');continue
                    word=str(data.get('word','')).strip().upper()
                    if not valid_word(word):
                        await error(ws,'Not an accepted English word. Names of people, places, brands and other proper names are not allowed.');continue
                    # Definition is display-only; the word stays valid if MW is unavailable.
                    result=await lookup_word(word) or {'definition':'Definition unavailable','partOfSpeech':None}
                    # Every claim searches ALL words, so no target click is needed.
                    # Prefer the largest extendable base word; ties favor a steal.
                    # If no extension is possible, try a new word from center letters.
                    full=Counter(word)
                    options=[]
                    for entry in room.words:
                        old=entry['word']
                        base=Counter(old)
                        if word==old or len(word)<=len(old): continue
                        if not all(full[c]>=n for c,n in base.items()): continue
                        if invalid_extension(old,word): continue
                        extra=+(full-base)
                        if all(room.center[c]>=n for c,n in extra.items()):
                            options.append((len(old),entry['owner']!=seat,-entry['id'],entry,extra))
                    if options:
                        _,_,_,matching,needed=max(options,key=lambda x:x[:3])
                    elif all(room.center[c]>=n for c,n in full.items()):
                        matching=None
                        needed=full
                    else:
                        await error(ws,'Cannot form that word using the center and an existing word. Plurals and tense-only changes are not allowed.');continue
                    # Consume exactly the visible center tiles used in this claim.
                    # A tile removed here vanishes from the central scattered pile.
                    removed=Counter()
                    for idx,letter in enumerate(room.bag):
                        if idx in room.revealed and idx not in room.used and removed[letter]<needed[letter]:
                            room.used.add(idx)
                            removed[letter]+=1
                    if removed!=needed:
                        await error(ws,'Center tiles are out of sync. Please try again.');continue
                    room.center.subtract(needed)
                    room.center=+room.center
                    is_steal = matching is not None and matching['owner'] != seat
                    if matching is not None:
                        room.words.remove(matching)
                        old=matching['word']
                        msg=(f'{room.names[seat]} extended {old} → {word} and earned the next flip!'
                             if matching['owner']==seat else
                             f'{room.names[seat]} stole {old} → {word} and earned the next flip!')
                    else:
                        msg=f'{room.names[seat]} claimed {word} and earned the next flip!'
                    points=word_points(word)
                    room.seq+=1
                    room.words.append({'id':room.seq,'word':word,'owner':seat,'points':points})
                    room.turn=seat  # Bonus flip, overriding the previous turn order.
                    room.latest_word={'word':word,'definition':result['definition'],'partOfSpeech':result['partOfSpeech'],'player':room.names[seat],'points':points}
                    room.last_effect={'id':room.seq,'kind':'steal' if is_steal else 'claim',
                                      'player':room.names[seat],'word':word,'points':points,
                                      'oldWord':matching['word'] if matching else None,
                                      'oldPoints':matching['points'] if matching else 0,
                                      'victim':room.names[matching['owner']] if is_steal else None}
                    room.message=f'{msg} (+{points} points)'
                    room.end_votes.clear()  # A word was found, so the stuck-board votes no longer apply.
                    start_turn_timer(room)
                    await check_game_over(room)
                    await broadcast(room)
                else:
                    await error(ws,'Unknown action.')
    except (WebSocketDisconnect, RuntimeError, ValueError, json.JSONDecodeError):
        pass
    finally:
        if room is not None and seat is not None:
            async with room.lock:
                if seat<len(room.sockets) and room.sockets[seat] is ws:
                    room.sockets[seat]=None
                    if room.turn==seat:
                        pass_turn(room)
                        start_turn_timer(room)
                    room.message=f'{room.names[seat]} disconnected.'
                    check_end_vote(room)  # Fewer players online can turn the existing votes into a majority.
                    await broadcast(room)
