import asyncio
import json
import random
import secrets
import string
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from wordfreq import zipf_frequency
from american_english import is_american_english_word

app = FastAPI()
ROOT = Path(__file__).resolve().parent
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')

# Original Bananagrams 144-tile English distribution.
TILE_COUNTS = {'A':13,'B':3,'C':3,'D':6,'E':18,'F':3,'G':4,'H':3,'I':12,'J':2,'K':2,'L':5,'M':3,'N':8,'O':11,'P':3,'Q':2,'R':9,'S':6,'T':9,'U':6,'V':3,'W':3,'X':2,'Y':3,'Z':2}
assert sum(TILE_COUNTS.values()) == 144
ROOMS = {}
MAX_PLAYERS = 8

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

    def board_public(self):
        return ['USED' if idx in self.used else letter if idx in self.revealed else None for idx, letter in enumerate(self.bag)]

    def public(self):
        return {'type':'state','code':self.code,'remaining':144-len(self.revealed),'center':dict(self.center),
                'words':self.words,'board':[letter if letter is not None else None for letter in self.board_public()], 'maxPlayers':MAX_PLAYERS,'players':[{'name':n,'connected':self.sockets[i] is not None} for i,n in enumerate(self.names)],
                'turn':self.turn,'message':self.message,'usedCount':len(self.used),
                'effect':self.last_effect}


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
    return (len(word) >= 3 and word.isascii() and word.isalpha()
            and is_american_english_word(word)
            and zipf_frequency(word.lower(), 'en') >= 2.0)


def invalid_extension(old,new):
    '''Block common plural and verb-inflection-only extensions; other meaningful anagrams are allowed.'''
    o,n = old.lower(),new.lower()
    if n in {o+'s',o+'es',o+'ed',o+'d',o+'ing',o+'er',o+'est'}: return True
    if o.endswith('y') and n in {o[:-1]+'ies',o[:-1]+'ied'}: return True
    if o.endswith('e') and n in {o[:-1]+'ing',o+'d'}: return True
    if len(o)>2 and o[-1] not in 'aeiou' and n in {o+o[-1]+'ed',o+o[-1]+'ing'}: return True
    if n in {o+'en',o+'n'}: return True
    return False

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
                    if len(room.names)>=MAX_PLAYERS:
                        await error(ws,'This room already has eight players.'); room=None;continue
                    seat=len(room.names)
                    room.names.append(name)
                    room.sockets.append(ws)
                    room.message = f'{name} joined! ' + (f'{len(room.names)} players ready. Start flipping!' if len(room.names)>=2 else 'Waiting for another player.')
                    await ws.send_json({'type':'welcome','seat':seat,'code':room.code})
                    await broadcast(room)
                continue
            async with room.lock:
                if action=='flip':
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
                    letter=room.bag[tile]
                    room.revealed.add(tile)
                    room.center[letter]+=1
                    room.turn=(room.turn+1)%len(room.names)
                    for _ in range(len(room.names)):
                        if room.sockets[room.turn] is not None: break
                        room.turn=(room.turn+1)%len(room.names)
                    room.message=f'{room.names[seat]} revealed {letter}. Everyone can race to claim words!'
                    await broadcast(room)
                elif action=='claim':
                    if len(room.names)<2:
                        await error(ws,'Wait for a second player to join.');continue
                    word=str(data.get('word','')).strip().upper()
                    if not valid_word(word):
                        await error(ws,'Enter a valid American English word of at least 3 letters.');continue
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
                    room.seq+=1
                    room.words.append({'id':room.seq,'word':word,'owner':seat})
                    room.turn=seat  # Bonus flip, overriding the previous turn order.
                    room.last_effect={'id':room.seq,'kind':'steal' if is_steal else 'claim',
                                      'player':room.names[seat],'word':word}
                    room.message=msg
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
                        for step in range(1,len(room.names)+1):
                            candidate=(seat+step)%len(room.names)
                            if room.sockets[candidate] is not None:
                                room.turn=candidate
                                break
                    room.message=f'{room.names[seat]} disconnected.'
                    await broadcast(room)
