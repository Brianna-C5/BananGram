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

app = FastAPI()
ROOT = Path(__file__).resolve().parent
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')

# Original Bananagrams 144-tile English distribution.
TILE_COUNTS = {'A':13,'B':3,'C':3,'D':6,'E':18,'F':3,'G':4,'H':3,'I':12,'J':2,'K':2,'L':5,'M':3,'N':8,'O':11,'P':3,'Q':2,'R':9,'S':6,'T':9,'U':6,'V':3,'W':3,'X':2,'Y':3,'Z':2}
assert sum(TILE_COUNTS.values()) == 144
ROOMS = {}

@dataclass
class Room:
    code: str
    bag: list = field(default_factory=list)
    center: Counter = field(default_factory=Counter)
    words: list = field(default_factory=list)
    names: list = field(default_factory=list)
    sockets: list = field(default_factory=list)
    turn: int = 0
    message: str = 'Invite a friend with the room code!'
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    seq: int = 0

    def public(self):
        return {'type':'state','code':self.code,'remaining':len(self.bag),'center':dict(self.center),
                'words':self.words,'players':[{'name':n,'connected':self.sockets[i] is not None} for i,n in enumerate(self.names)],
                'turn':self.turn,'message':self.message}


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
    return len(word)>=3 and word.isalpha() and zipf_frequency(word.lower(),'en')>=2.0


def invalid_extension(old,new):
    '''Block common plural and verb-inflection-only extensions; other meaningful anagrams are allowed.'''
    o,n = old.lower(),new.lower()
    if n in {o+'s',o+'es',o+'ed',o+'d',o+'ing',o+'er',o+'est'}: return True
    if o.endswith('y') and n in {o[:-1]+'ies',o[:-1]+'ied'}: return True
    if o.endswith('e') and n in {o[:-1]+'ing',o+'d'}: return True
    if len(o)>2 and o[-1] not in 'aeiou' and n in {o+o[-1]+'ed',o+o[-1]+'ing'}: return True
    if n in {o+'en',o+'n'}: return True
    # Reject inflection when letter inventory matches an inflected spelling, even if shuffled.
    variants={o+'s',o+'es',o+'ed',o+'d',o+'ing',o+'er',o+'est',o+'en',o+'n'}
    if o.endswith('y'): variants.update([o[:-1]+'ies',o[:-1]+'ied'])
    if o.endswith('e'): variants.add(o[:-1]+'ing')
    if len(o)>2: variants.update([o+o[-1]+'ed',o+o[-1]+'ing'])
    return any(Counter(v)==Counter(n) for v in variants)

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
                    if len(room.names)>=2:
                        await error(ws,'This room already has two players.'); room=None;continue
                    seat=len(room.names)
                    room.names.append(name)
                    room.sockets.append(ws)
                    room.message = f'{name} joined! ' + ('Both players are here. Start flipping!' if len(room.names)==2 else 'Waiting for another player.')
                    await ws.send_json({'type':'welcome','seat':seat,'code':room.code})
                    await broadcast(room)
                continue
            async with room.lock:
                if action=='flip':
                    if len(room.names)<2:
                        await error(ws,'Wait for a second player to join.');continue
                    if seat != room.turn:
                        await error(ws,'It is not your turn to flip.');continue
                    if not room.bag:
                        await error(ws,'All tiles have been revealed.');continue
                    letter=room.bag.pop()
                    room.center[letter]+=1
                    room.turn=1-room.turn
                    room.message=f'{room.names[seat]} revealed {letter}. Both players can claim words!'
                    await broadcast(room)
                elif action=='claim':
                    if len(room.names)<2:
                        await error(ws,'Wait for a second player to join.');continue
                    word=str(data.get('word','')).strip().upper()
                    if not valid_word(word):
                        await error(ws,'Enter a valid English word of at least 3 letters.');continue
                    target=data.get('target')
                    needed=Counter(word)
                    if target is not None:
                        matching=next((entry for entry in room.words if entry['id']==target),None)
                        if matching is None:
                            await error(ws,'That word has already been taken.');continue
                        if matching['owner']==seat:
                            await error(ws,'Choose an opponent’s word to steal.');continue
                        old=matching['word']
                        base=Counter(old)
                        if not all(needed[c]>=v for c,v in base.items()) or sum(needed.values())<=len(old):
                            await error(ws,'Keep every old letter and add at least one new letter.');continue
                        if invalid_extension(old,word):
                            await error(ws,'No simple plurals or tense changes. Make a new word!');continue
                        needed.subtract(base)
                        needed=+needed
                    if any(room.center[c]<n for c,n in needed.items()):
                        await error(ws,'Not enough letters in the center for that word.');continue
                    room.center.subtract(needed)
                    room.center=+room.center
                    if target is not None:
                        room.words.remove(matching)
                        msg=f'{room.names[seat]} stole {old} → {word}!'
                    else:
                        msg=f'{room.names[seat]} claimed {word}!'
                    room.seq+=1
                    room.words.append({'id':room.seq,'word':word,'owner':seat})
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
                    room.message=f'{room.names[seat]} disconnected.'
                    await broadcast(room)
