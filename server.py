"""
Vocaloid Song Guessing Game - Backend Server
FastAPI + SQLite + WebSocket Multiplayer
"""

import json
import random
import sqlite3
import time
import hashlib
import asyncio
from typing import Optional, Dict
from datetime import date
from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from database import init_db, get_db, VOCALOID_COMPANY, GENRE_SIMILARITY

app = FastAPI(title="Vocaloid猜曲子")

# ===== Multiplayer State =====
# room_code -> room state
rooms: Dict[str, dict] = {}
# websocket connections by room
connections: Dict[str, Dict[str, WebSocket]] = {}
# room locks for thread safety
room_locks: Dict[str, asyncio.Lock] = {}

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()

# Determine view tier
TIER_RANK = {'神话': 5, '传说': 4, '殿堂': 3, '人气': 2, '普通': 1}

def view_tier(tier_or_views):
    """Return tier label from tier string or views number."""
    if isinstance(tier_or_views, str) and tier_or_views in TIER_RANK:
        return tier_or_views
    views = tier_or_views or 0
    if views >= 10_000_000:
        return '神话'
    elif views >= 1_000_000:
        return '传说'
    elif views >= 100_000:
        return '殿堂'
    else:
        return '普通'

def view_tier_num(tier_or_views):
    if isinstance(tier_or_views, str) and tier_or_views in TIER_RANK:
        return TIER_RANK[tier_or_views]
    views = tier_or_views or 0
    if views >= 10_000_000:
        return 5
    elif views >= 1_000_000:
        return 4
    elif views >= 100_000:
        return 3
    else:
        return 1

def bpm_category(bpm):
    if bpm >= 180:
        return '超快 (≥180)'
    elif bpm >= 140:
        return '快速 (140-179)'
    elif bpm >= 100:
        return '中速 (100-139)'
    else:
        return '慢速 (<100)'

def bpm_cat_num(bpm):
    if bpm >= 180:
        return 4
    elif bpm >= 140:
        return 3
    elif bpm >= 100:
        return 2
    else:
        return 1

def genre_group(genre):
    for group, members in GENRE_SIMILARITY.items():
        if genre in members:
            return group
    return genre

def compare_attribute(attr_name, guess_val, target_val):
    """Compare a single attribute and return result.
    Returns: {value, color: 'green'|'yellow'|'gray', arrow: 'up'|'down'|None}
    """
    result = {'value': str(guess_val), 'color': 'gray', 'arrow': None}
    
    if attr_name == 'producer':
        if guess_val == target_val:
            result['color'] = 'green'
        # No yellow for producer - it's either exact or not
    
    elif attr_name == 'vocaloid':
        if guess_val == target_val:
            result['color'] = 'green'
        else:
            # Same company = yellow
            guess_company = VOCALOID_COMPANY.get(guess_val)
            target_company = VOCALOID_COMPANY.get(target_val)
            if guess_company and target_company and guess_company == target_company:
                result['color'] = 'yellow'
    
    elif attr_name == 'release_year':
        if guess_val == target_val:
            result['color'] = 'green'
        elif abs(guess_val - target_val) <= 2:
            result['color'] = 'yellow'
        if guess_val < target_val:
            result['arrow'] = 'up'
        elif guess_val > target_val:
            result['arrow'] = 'down'
    
    elif attr_name == 'language':
        if guess_val == target_val:
            result['color'] = 'green'
        # No yellow for language
    
    elif attr_name == 'nico_tier':
        guess_tier = view_tier_num(guess_val)
        target_tier = view_tier_num(target_val)
        if guess_tier == target_tier:
            result['color'] = 'green'
        elif abs(guess_tier - target_tier) == 1:
            result['color'] = 'yellow'
        if guess_tier < target_tier:
            result['arrow'] = 'up'
        elif guess_tier > target_tier:
            result['arrow'] = 'down'
    
    elif attr_name == 'length_sec':
        if guess_val <= 0 or target_val <= 0:
            # Missing data, can't compare
            result['color'] = 'gray'
            result['value'] = '?'
        elif guess_val == target_val:
            result['color'] = 'green'
        elif abs(guess_val - target_val) <= 30:
            result['color'] = 'yellow'
        if guess_val < target_val:
            result['arrow'] = 'up'
        elif guess_val > target_val:
            result['arrow'] = 'down'
    
    return result


# ----- API Routes -----

@app.get("/api/search")
def search_songs(q: str = ""):
    """Search songs by title (Chinese/Japanese/English) or producer"""
    if not q or len(q.strip()) < 1:
        return []
    
    conn = get_db()
    c = conn.cursor()
    
    like_q = f'%{q}%'
    c.execute('''SELECT id, title, title_jp, title_cn, producer, vocaloid, release_year
                 FROM songs 
                 WHERE title LIKE ? 
                    OR title_jp LIKE ? 
                    OR title_cn LIKE ? 
                    OR producer LIKE ?
                    OR vocaloid LIKE ?
                 ORDER BY nico_views DESC
                 LIMIT 15''', 
              (like_q, like_q, like_q, like_q, like_q))
    
    results = []
    for row in c.fetchall():
        results.append({
            'id': row['id'],
            'title': row['title'],
            'title_jp': row['title_jp'],
            'title_cn': row['title_cn'],
            'producer': row['producer'],
            'vocaloid': row['vocaloid'],
            'release_year': row['release_year'],
            'display': f"{row['title']} / {row['title_jp']} — {row['producer']} feat. {row['vocaloid']}"
        })
    conn.close()
    return results


@app.get("/api/new_game")
def new_game(difficulty: str = "normal"):
    """Start a new game"""
    conn = get_db()
    c = conn.cursor()
    
    # Determine pool based on difficulty
    pool_queries = {
        # 日文传说
        'ja_legend': "SELECT id FROM songs WHERE language = 'ja' AND tier = '传说'",
        # 所有传说
        'all_legend': "SELECT id FROM songs WHERE tier = '传说'",
        # 中文传说
        'zh_legend': "SELECT id FROM songs WHERE language = 'zh' AND tier = '传说'",
        # 中文殿堂
        'zh_hall': "SELECT id FROM songs WHERE language = 'zh' AND tier = '殿堂'",
        # 所有神话
        'all_myth': "SELECT id FROM songs WHERE tier = '神话'",
    }
    if difficulty in pool_queries:
        c.execute(pool_queries[difficulty])
        pool = [row['id'] for row in c.fetchall()]
        if not pool:
            conn.close()
            raise HTTPException(status_code=500, detail="No songs in database for this difficulty")
        if difficulty == 'daily':
            today = date.today().isoformat()
            hash_val = int(hashlib.md5(today.encode()).hexdigest(), 16)
            target_id = pool[hash_val % len(pool)]
        else:
            target_id = random.choice(pool)
        max_guesses = 8
    else:
        # fallback: all legend
        c.execute("SELECT id FROM songs WHERE tier = '传说'")
        pool = [row['id'] for row in c.fetchall()]
        if not pool:
            conn.close()
            raise HTTPException(status_code=500, detail="No songs in database")
        target_id = random.choice(pool)
        max_guesses = 8

    # Reset game state
    c.execute('DELETE FROM game_state')
    c.execute('DELETE FROM guess_history')
    c.execute('''INSERT INTO game_state (target_song_id, difficulty, guesses_used, max_guesses, status)
                 VALUES (?, ?, 0, ?, 'playing')''', (target_id, difficulty, max_guesses))
    conn.commit()
    
    # Return some info
    c.execute('SELECT COUNT(*) FROM songs')
    total_songs = c.fetchone()[0]
    conn.close()
    
    return {
        'status': 'new_game',
        'difficulty': difficulty,
        'max_guesses': max_guesses,
        'total_songs': total_songs,
        'pool_size': len(pool)
    }


@app.get("/api/game_state")
def get_game_state():
    """Get current game state (for reconnection)"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM game_state WHERE id = 1')
    state = c.fetchone()
    
    if not state:
        conn.close()
        return {'status': 'no_game'}
    
    # Get guess history
    c.execute('''SELECT gh.guess_number, gh.song_id, gh.result_json
                 FROM guess_history gh
                 WHERE gh.game_id = 1
                 ORDER BY gh.guess_number''')
    guesses = []
    for row in c.fetchall():
        if row['result_json']:
            try:
                guesses.append(json.loads(row['result_json']))
            except:
                pass
    
    conn.close()
    
    return {
        'status': state['status'],
        'difficulty': state['difficulty'],
        'guesses_used': state['guesses_used'],
        'max_guesses': state['max_guesses'],
        'guesses': guesses
    }


@app.get("/api/guess")
def make_guess(song_id: int):
    """Make a guess"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE id = 1')
    state = c.fetchone()
    
    if not state or state['status'] != 'playing':
        conn.close()
        raise HTTPException(status_code=400, detail="No active game")
    
    # Get guess song
    c.execute('SELECT * FROM songs WHERE id = ?', (song_id,))
    guess_song = c.fetchone()
    if not guess_song:
        conn.close()
        raise HTTPException(status_code=404, detail="Song not found")
    
    # Check if this song was already guessed (would need a guesses table)
    # For now, we skip this check as we don't track individual guesses in SQL
    
    # Get target song
    c.execute('SELECT * FROM songs WHERE id = ?', (state['target_song_id'],))
    target_song = c.fetchone()
    
    # Build comparison results (7 attributes)
    attributes = [
        {'name': '作者', 'key': 'producer', 'guess': guess_song['producer'], 'target': target_song['producer']},
        {'name': '虚拟歌手', 'key': 'vocaloid', 'guess': guess_song['vocaloid'], 'target': target_song['vocaloid']},
        {'name': '发行年份', 'key': 'release_year', 'guess': guess_song['release_year'], 'target': target_song['release_year']},
        {'name': '语言', 'key': 'language', 'guess': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(guess_song['language'], guess_song['language']), 
         'target': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(target_song['language'], target_song['language'])},
        {'name': '级别', 'key': 'nico_tier', 'guess': guess_song['tier'] or guess_song['nico_views'], 'target': target_song['tier'] or target_song['nico_views']},
        {'name': '曲长', 'key': 'length_sec', 'guess': guess_song['length_sec'], 'target': target_song['length_sec']},
    ]
    
    results = []
    for attr in attributes:
        cmp = compare_attribute(attr['key'], attr['guess'], attr['target'])
        cmp['name'] = attr['name']
        if attr['key'] == 'nico_tier':
            cmp['value'] = view_tier(attr['guess'])
            cmp['views'] = guess_song['nico_views']
        elif attr['key'] == 'length_sec':
            if attr['guess'] > 0:
                guess_min = attr['guess'] // 60
                guess_sec = attr['guess'] % 60
                cmp['value'] = f"{guess_min}:{guess_sec:02d}"
            else:
                cmp['value'] = '?'
        results.append(cmp)
    
    # Check if won
    is_correct = (guess_song['id'] == target_song['id'])
    new_guesses = state['guesses_used'] + 1
    new_status = 'won' if is_correct else ('lost' if new_guesses >= state['max_guesses'] else 'playing')
    
    c.execute('UPDATE game_state SET guesses_used = ?, status = ? WHERE id = 1',
              (new_guesses, new_status))
    conn.commit()
    
    response = {
        'is_correct': is_correct,
        'guesses_used': new_guesses,
        'max_guesses': state['max_guesses'],
        'status': new_status,
        'guess_song': {
            'title': guess_song['title'],
            'title_jp': guess_song['title_jp'],
            'title_cn': guess_song['title_cn'],
            'producer': guess_song['producer'],
            'vocaloid': guess_song['vocaloid'],
            'views': guess_song['nico_views'],
        },
        'attributes': results,
    }
    
    if new_status in ('won', 'lost'):
        response['target_song'] = {
            'title': target_song['title'],
            'title_jp': target_song['title_jp'],
            'title_cn': target_song['title_cn'],
            'producer': target_song['producer'],
            'vocaloid': target_song['vocaloid'],
            'release_year': target_song['release_year'],
            'language': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(target_song['language'], target_song['language']),
            'bpm': target_song['bpm'],
            'views': target_song['nico_views'],
            'nico_views': target_song['nico_views'],
            'genre': target_song['genre'],
            'length_sec': target_song['length_sec'],
        }
    
    # Save guess history with results
    history_json = json.dumps({
        'guess_number': new_guesses,
        'song_id': song_id,
        'guess_song': response['guess_song'],
        'attributes': response['attributes'],
        'is_correct': is_correct,
    }, ensure_ascii=False)
    c.execute('INSERT INTO guess_history (game_id, guess_number, song_id, result_json) VALUES (1, ?, ?, ?)',
              (new_guesses, song_id, history_json))
    conn.commit()
    
    conn.close()
    return response


@app.get("/api/hint")
def get_hint():
    """Get a hint (reveals one random attribute of the target)"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM game_state WHERE id = 1')
    state = c.fetchone()
    
    if not state or state['status'] != 'playing':
        conn.close()
        raise HTTPException(status_code=400, detail="No active game")
    
    c.execute('SELECT * FROM songs WHERE id = ?', (state['target_song_id'],))
    target = c.fetchone()
    conn.close()
    
    length_min, length_sec = divmod(target['length_sec'] or 0, 60)
    hints = [
        {'name': '作者', 'value': target['producer']},
        {'name': '虚拟歌手', 'value': target['vocaloid']},
        {'name': '发行年份', 'value': str(target['release_year'])},
        {'name': '语言', 'value': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(target['language'], target['language'])},
        {'name': '级别', 'value': view_tier(target['tier'] if target['tier'] else target['nico_views'])},
        {'name': '曲长', 'value': f"{length_min}:{length_sec:02d}" if (target['length_sec'] or 0) > 0 else '?'},
    ]
    
    return random.choice(hints)


@app.get("/api/song/{song_id}")
def get_song(song_id: int):
    """Get detailed info about a song"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM songs WHERE id = ?', (song_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Song not found")
    return {
        'id': row['id'],
        'title': row['title'],
        'title_jp': row['title_jp'],
        'title_cn': row['title_cn'],
        'producer': row['producer'],
        'vocaloid': row['vocaloid'],
        'release_year': row['release_year'],
        'language': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(row['language'], row['language']),
        'bpm': row['bpm'],
        'nico_views': row['nico_views'],
        'genre': row['genre'],
        'length_sec': row['length_sec'],
    }


# ===== Multiplayer API =====

def generate_room_code():
    """Generate a 5-digit room code"""
    return ''.join([str(random.randint(0, 9)) for _ in range(5)])

def get_target_for_round(room):
    """Pick a random song for the current round based on room difficulty"""
    conn = get_db()
    c = conn.cursor()
    
    diff = room.get('difficulty', 'all_legend')
    pool_queries = {
        'ja_legend': "SELECT id FROM songs WHERE language = 'ja' AND tier = '传说'",
        'all_legend': "SELECT id FROM songs WHERE tier = '传说'",
        'zh_legend': "SELECT id FROM songs WHERE language = 'zh' AND tier = '传说'",
        'zh_hall': "SELECT id FROM songs WHERE language = 'zh' AND tier = '殿堂'",
        'all_myth': "SELECT id FROM songs WHERE tier = '神话'",
    }
    query = pool_queries.get(diff, pool_queries['all_legend'])
    c.execute(query)
    pool = [row['id'] for row in c.fetchall()]
    conn.close()
    if not pool:
        return random.choice([1])  # fallback
    return random.choice(pool)

def build_comparison(guess_song, target_song):
    """Build comparison results for a guess"""
    attributes = [
        {'name': '作者', 'key': 'producer', 'guess': guess_song['producer'], 'target': target_song['producer']},
        {'name': '虚拟歌手', 'key': 'vocaloid', 'guess': guess_song['vocaloid'], 'target': target_song['vocaloid']},
        {'name': '发行年份', 'key': 'release_year', 'guess': guess_song['release_year'], 'target': target_song['release_year']},
        {'name': '语言', 'key': 'language', 'guess': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(guess_song['language'], guess_song['language']), 
         'target': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(target_song['language'], target_song['language'])},
        {'name': 'BPM', 'key': 'bpm', 'guess': guess_song['bpm'], 'target': target_song['bpm']},
        {'name': '级别', 'key': 'nico_tier', 'guess': guess_song['tier'] or guess_song['nico_views'], 'target': target_song['tier'] or target_song['nico_views']},
        {'name': '曲风', 'key': 'genre', 'guess': guess_song['genre'], 'target': target_song['genre']},
        {'name': '曲长(秒)', 'key': 'length_sec', 'guess': guess_song['length_sec'], 'target': target_song['length_sec']},
    ]
    
    results = []
    for attr in attributes:
        cmp = compare_attribute(attr['key'], attr['guess'], attr['target'])
        cmp['name'] = attr['name']
        if attr['key'] == 'nico_tier':
            cmp['value'] = view_tier(attr['guess'])
            cmp['views'] = guess_song['nico_views']
        elif attr['key'] == 'length_sec':
            if attr['guess'] > 0:
                guess_min = attr['guess'] // 60
                guess_sec = attr['guess'] % 60
                cmp['value'] = f"{guess_min}:{guess_sec:02d}"
            else:
                cmp['value'] = '?'
        results.append(cmp)
    
    return results


@app.get("/api/mp/create_room")
def create_room(match_format: int = 3, difficulty: str = "all_legend"):
    """Create a multiplayer room"""
    if match_format not in (1, 3, 5, 7):
        raise HTTPException(status_code=400, detail="Invalid format. Must be 1, 3, 5, or 7.")
    
    valid_diffs = ('ja_legend', 'all_legend', 'zh_legend', 'zh_hall', 'all_myth')
    if difficulty not in valid_diffs:
        difficulty = 'all_legend'
    
    # Generate unique room code
    for _ in range(100):
        code = generate_room_code()
        if code not in rooms:
            break
    else:
        raise HTTPException(status_code=500, detail="Could not generate room code")
    
    rooms[code] = {
        'code': code,
        'match_format': match_format,
        'total_rounds': match_format,
        'difficulty': difficulty,
        'players': {},
        'current_round': 0,
        'round_target': None,
        'round_start_time': None,
        'round_guesses': {},
        'round_status': 'waiting',
        'match_status': 'waiting',
        'winner': None,
    }
    connections[code] = {}
    room_locks[code] = asyncio.Lock()
    
    return {
        'room_code': code,
        'match_format': match_format,
        'difficulty': difficulty,
    }


@app.get("/api/mp/room_info")
def room_info(code: str):
    """Get room info"""
    if code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[code]
    return {
        'room_code': code,
        'match_format': room['match_format'],
        'total_rounds': room['total_rounds'],
        'current_round': room['current_round'],
        'match_status': room['match_status'],
        'round_status': room['round_status'],
        'difficulty': room.get('difficulty', 'all_legend'),
        'host_id': room.get('host_id'),
        'players': [{'id': pid, 'name': p['name'], 'score': p['score'], 'connected': p['connected']} 
                     for pid, p in room['players'].items()],
    }


# ===== WebSocket Endpoint =====

@app.websocket("/ws/{room_code}/{player_id}")
async def websocket_endpoint(ws: WebSocket, room_code: str, player_id: str):
    await ws.accept()
    
    # Validate room
    if room_code not in rooms:
        await ws.send_json({'type': 'error', 'message': '房间不存在'})
        await ws.close()
        return
    
    room = rooms[room_code]
    lock = room_locks[room_code]
    
    # Register connection
    async with lock:
        connections[room_code][player_id] = ws
        if player_id in room['players']:
            room['players'][player_id]['connected'] = True
            room['players'][player_id]['last_seen'] = time.time()
        else:
            if 'host_id' not in room:
                room['host_id'] = player_id
            room['players'][player_id] = {
                'name': f'玩家{len(room["players"]) + 1}',
                'score': 0,
                'connected': True,
                'last_seen': time.time(),
                'ready': False,
            }
        
        player_count = len(room['players'])
    
    # Notify all players in room
    await broadcast_room_state(room_code)
    
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get('type')
            
            if msg_type == 'ping':
                await ws.send_json({'type': 'pong'})
                async with lock:
                    if player_id in room['players']:
                        room['players'][player_id]['last_seen'] = time.time()
            
            elif msg_type == 'ready':
                async with lock:
                    if player_id in room['players']:
                        room['players'][player_id]['ready'] = True
                await broadcast_room_state(room_code)
            
            elif msg_type == 'start_match':
                if room.get('host_id') == player_id:
                    connected = {pid: p for pid, p in room['players'].items() if p.get('connected')}
                    all_ready = len(connected) >= 2 and all(p.get('ready') for p in connected.values())
                    if all_ready and room['match_status'] == 'waiting':
                        await start_match(room_code)
                    else:
                        await ws.send_json({'type': 'error', 'message': '等待所有玩家准备'})
            
            elif msg_type == 'guess':
                if room['round_status'] != 'playing':
                    await ws.send_json({'type': 'error', 'message': '当前不在对局中'})
                    continue
                
                song_id = data.get('song_id')
                if not song_id:
                    continue
                
                await handle_mp_guess(room_code, player_id, song_id)
            
            elif msg_type == 'surrender':
                await handle_surrender(room_code, player_id)
            
            elif msg_type == 'next_round':
                if room.get('host_id') == player_id and room['match_status'] == 'finished':
                    await reset_match(room_code)
            
            elif msg_type == 'change_difficulty':
                if room.get('host_id') == player_id and room['match_status'] == 'waiting':
                    new_diff = data.get('difficulty', 'all_legend')
                    if new_diff in ('ja_legend', 'all_legend', 'zh_legend', 'zh_hall', 'all_myth'):
                        async with lock:
                            room['difficulty'] = new_diff
                    await broadcast_room_state(room_code)
            
            elif msg_type == 'leave':
                break
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Handle disconnect
        async with lock:
            if room_code in connections and player_id in connections[room_code]:
                del connections[room_code][player_id]
            if room_code in rooms and player_id in rooms[room_code]['players']:
                room['players'][player_id]['connected'] = False
                room['players'][player_id]['last_seen'] = time.time()
        
        await broadcast_room_state(room_code)
        
        # Start 30s countdown for disconnect forfeit
        asyncio.create_task(check_disconnect_forfeit(room_code, player_id))


async def handle_surrender(room_code: str, player_id: str):
    """Player surrenders the current round (not the whole match)."""
    room = rooms[room_code]
    if room['match_status'] != 'playing' or room['round_status'] != 'playing':
        return
    
    async with room_locks[room_code]:
        room.setdefault('round_surrendered', set()).add(player_id)
        # active = connected and not surrendered this round
        active = {pid for pid, p in room['players'].items()
                  if p.get('connected') and pid not in room.get('round_surrendered', set())}
    
    # If only one active player left, that player wins the round and answer is shown.
    if len(active) <= 1:
        winner = active.pop() if active else None
        await end_round(room_code, winner, reason='surrender')
    else:
        # Others still playing; only notify the surrender.
        for pid in connections.get(room_code, {}):
            try:
                await connections[room_code][pid].send_json({
                    'type': 'surrender_notice',
                    'player_id': player_id,
                    'round_over': False,
                })
            except:
                pass


async def reset_match(room_code: str):
    """Host starts a fresh match in the same room."""
    room = rooms[room_code]
    room['match_status'] = 'playing'
    room['current_round'] = 0
    room['winner'] = None
    room.pop('surrendered', None)
    for p in room['players'].values():
        p['score'] = 0
        p['ready'] = False
    
    await broadcast_room_state(room_code)
    await start_round(room_code)


async def broadcast_room_state(room_code: str):
    """Send room state to all connected players"""
    if room_code not in rooms:
        return
    room = rooms[room_code]
    
    players_info = {}
    for pid, p in room['players'].items():
        players_info[pid] = {
            'name': p['name'],
            'score': p['score'],
            'connected': p['connected'],
            'ready': p.get('ready', False),
        }
    
    state_msg = {
        'type': 'room_state',
        'room_code': room_code,
        'match_format': room['match_format'],
        'total_rounds': room['total_rounds'],
        'current_round': room['current_round'],
        'match_status': room['match_status'],
        'round_status': room['round_status'],
        'players': players_info,
        'winner': room.get('winner'),
        'host_id': room.get('host_id'),
        'difficulty': room.get('difficulty', 'all_legend'),
    }
    
    if room['round_status'] == 'playing' and room['round_start_time']:
        elapsed = time.time() - room['round_start_time']
        remaining = max(0, 120 - int(elapsed))
        state_msg['timer_remaining'] = remaining
    
    to_remove = []
    for pid, ws in connections.get(room_code, {}).items():
        try:
            await ws.send_json(state_msg)
        except:
            to_remove.append(pid)
    
    for pid in to_remove:
        if pid in connections.get(room_code, {}):
            del connections[room_code][pid]


async def start_match(room_code: str):
    """Start a new match"""
    room = rooms[room_code]
    room['match_status'] = 'playing'
    room['current_round'] = 0
    room['winner'] = None
    room.pop('surrendered', None)
    for p in room['players'].values():
        p['score'] = 0
        p['ready'] = False
    
    await broadcast_room_state(room_code)
    await start_round(room_code)


async def start_round(room_code: str):
    """Start a new round"""
    room = rooms[room_code]
    room['current_round'] += 1
    room['round_status'] = 'playing'
    room['round_guesses'] = {}
    room['round_surrendered'] = set()
    room['round_start_time'] = time.time()
    room['round_token'] = room.get('round_token', 0) + 1
    
    # Pick target song
    target_id = get_target_for_round(room)
    room['round_target'] = target_id
    
    # Notify players
    for pid in connections.get(room_code, {}):
        try:
            await connections[room_code][pid].send_json({
                'type': 'round_start',
                'round': room['current_round'],
                'total_rounds': room['total_rounds'],
                'timer': 120,
            })
        except:
            pass
    
    # Start timer task
    asyncio.create_task(round_timer(room_code, room['round_token']))


async def round_timer(room_code: str, round_num: int):
    """120-second round timer"""
    await asyncio.sleep(120)
    
    if room_code not in rooms:
        return
    
    room = rooms[room_code]
    if room['current_round'] != round_num:
        return
    if room['round_token'] != round_num:
        return
    if room['round_status'] != 'playing':
        return
    
    await end_round(room_code, None, reason='timeout')


async def handle_mp_guess(room_code: str, player_id: str, song_id: int):
    """Handle a guess in multiplayer"""
    room = rooms[room_code]
    
    if room['round_status'] != 'playing':
        return
    
    # Get song info
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM songs WHERE id = ?', (song_id,))
    guess_song = c.fetchone()
    c.execute('SELECT * FROM songs WHERE id = ?', (room['round_target'],))
    target_song = c.fetchone()
    conn.close()
    
    if not guess_song or not target_song:
        return
    
    # Build comparison
    results = build_comparison(guess_song, target_song)
    is_correct = (song_id == room['round_target'])
    
    # Track guesses
    if player_id not in room['round_guesses']:
        room['round_guesses'][player_id] = []
    room['round_guesses'][player_id].append({
        'song_id': song_id,
        'title': guess_song['title'],
        'title_jp': guess_song['title_jp'],
        'title_cn': guess_song['title_cn'],
        'producer': guess_song['producer'],
        'vocaloid': guess_song['vocaloid'],
        'attributes': results,
        'is_correct': is_correct,
    })
    
    # Send result to the guesser
    if player_id in connections.get(room_code, {}):
        try:
            await connections[room_code][player_id].send_json({
                'type': 'guess_result',
                'guess_number': len(room['round_guesses'][player_id]),
                'is_correct': is_correct,
                'guess_song': {
                    'title': guess_song['title'],
                    'title_jp': guess_song['title_jp'],
                    'title_cn': guess_song['title_cn'],
                    'producer': guess_song['producer'],
                    'vocaloid': guess_song['vocaloid'],
                },
                'attributes': results,
            })
        except:
            pass
    
    # Notify all other players about the guess (without revealing details)
    for pid in room['players']:
        if pid != player_id and pid in connections.get(room_code, {}):
            try:
                await connections[room_code][pid].send_json({
                    'type': 'opponent_guess',
                    'player_id': player_id,
                    'guess_count': len(room['round_guesses'][player_id]),
                })
            except:
                pass
    
    # Check if correct
    if is_correct:
        await end_round(room_code, player_id)


async def end_round(room_code: str, winner_id: str | None, reason: str = 'guessed'):
    """End the current round"""
    room = rooms[room_code]
    if room['round_status'] != 'playing':
        return
    room['round_status'] = 'finished'
    room['round_token'] = room.get('round_token', 0) + 1  # invalidate timer
    
    if winner_id and winner_id in room['players']:
        room['players'][winner_id]['score'] += 1
    
    # Get target song info
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM songs WHERE id = ?', (room['round_target'],))
    target = c.fetchone()
    conn.close()
    
    target_info = None
    if target:
        target_info = {
            'title': target['title'],
            'title_jp': target['title_jp'],
            'title_cn': target['title_cn'],
            'producer': target['producer'],
            'vocaloid': target['vocaloid'],
            'release_year': target['release_year'],
            'language': {'ja': '日语', 'zh': '中文', 'en': '英语', 'ko': '韩语'}.get(target['language'], target['language']),
            'bpm': target['bpm'],
            'genre': target['genre'],
            'length_sec': target['length_sec'],
        }
    
    # Check if match is over
    needed_wins = room['total_rounds'] // 2 + 1
    match_over = False
    match_winner = None
    
    for pid, p in room['players'].items():
        if p['score'] >= needed_wins:
            match_over = True
            match_winner = pid
            room['winner'] = pid
            break
    
    # Also check if only one player can still reach needed wins
    if not match_over:
        remaining_rounds = room['total_rounds'] - room['current_round']
        can_win = [pid for pid, p in room['players'].items() if p['score'] + remaining_rounds >= needed_wins]
        if len(can_win) == 1:
            match_over = True
            match_winner = can_win[0]
            room['winner'] = can_win[0]
    
    if match_over:
        room['match_status'] = 'finished'
    
    # Broadcast round end
    for pid in connections.get(room_code, {}):
        try:
            await connections[room_code][pid].send_json({
                'type': 'round_end',
                'round': room['current_round'],
                'winner_id': winner_id,
                'reason': reason,
                'target_song': target_info,
                'scores': {p: room['players'][p]['score'] for p in room['players']},
                'match_over': match_over,
                'match_winner': match_winner,
            })
        except:
            pass
    
    await broadcast_room_state(room_code)
    
    # Auto-start next round after 5 seconds if match not over
    if not match_over:
        async def schedule_next(rc, rn):
            await asyncio.sleep(5)
            if rc in rooms:
                r = rooms[rc]
                if r['match_status'] == 'playing' and r['round_status'] == 'finished' and r['current_round'] == rn:
                    await start_round(rc)
        asyncio.create_task(schedule_next(room_code, room['current_round']))


async def check_disconnect_forfeit(room_code: str, player_id: str):
    """Check if disconnected player should forfeit after 30s"""
    await asyncio.sleep(30)
    
    if room_code not in rooms:
        return
    
    room = rooms[room_code]
    if player_id not in room['players']:
        return
    
    player = room['players'][player_id]
    if not player['connected'] and room['match_status'] == 'playing':
        # Player has been disconnected for 30s
        remaining = [pid for pid in room['players'] if pid != player_id and room['players'][pid].get('connected')]
        
        if len(remaining) <= 1:
            # Only 1 or 0 connected players left - forfeit match
            winner = remaining[0] if remaining else None
            room['winner'] = winner
            room['match_status'] = 'finished'
            room['round_status'] = 'finished'
        
        for pid in connections.get(room_code, {}):
            try:
                await connections[room_code][pid].send_json({
                    'type': 'player_disconnect_forfeit',
                    'player_id': player_id,
                    'winner_id': winner if len(remaining) <= 1 else None,
                })
            except:
                pass
        
        if len(remaining) <= 1:
            await broadcast_room_state(room_code)


# Mount static files
app.mount("/static", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
def root():
    return HTMLResponse(content=open('static/index.html', 'r', encoding='utf-8').read())


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
