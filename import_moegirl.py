"""
Import Vocaloid songs from 萌娘百科 (Moegirl Wiki)
Parses the famed-song-card divs from legend/hall pages.

Usage:
    python3 import_moegirl.py
"""

import urllib.request
import urllib.parse
import re
import sqlite3
import time

DATABASE = 'songs.db'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

# Map Chinese vocaloid names to Japanese
VOCALOID_NAME_MAP = {
    '初音未来': '初音ミク',
    '镜音铃': '鏡音リン',
    '镜音连': '鏡音レン',
    '巡音流歌': '巡音ルカ',
    'MEIKO': 'MEIKO',
    'KAITO': 'KAITO',
    'GUMI': 'GUMI',
    '神威乐步': 'がくっぽいど',
    '乐正绫': '楽正綾',
    '乐正龙牙': '楽正龍牙',
    '言和': '言和',
    '洛天依': '洛天依',
    '心华': '心華',
    'IA': 'IA',
    'MAYU': 'MAYU',
    'VY1': 'VY1',
    '结月缘': '結月ゆかり',
    'flower': 'flower',
    'Fukase': 'Fukase',
    '音街鳗': '音街ウナ',
    '星尘': '星尘',
    '初音未来': '初音ミク',
    '镜音铃': '鏡音リン',
    '镜音连': '鏡音レン',
    '巡音流歌': '巡音ルカ',
    '合唱或真人': '多人',
}

def fetch_page(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=30)
            return resp.read().decode('utf-8')
        except Exception as e:
            print(f"    Retry {i+1}/{retries}: {e}")
            time.sleep(2)
    return None

def parse_song_cards(html, is_chinese=False):
    songs = []
    
    # Try Japanese-style cards first
    card_pattern = r'<div class="famed-song-card">(.*?)</div>\s*</div>\s*</div>'
    cards = re.findall(card_pattern, html, re.DOTALL)
    
    if not cards and is_chinese:
        # Chinese pages use a different structure
        # Find all song entries by locating '曲目' patterns
        # Each entry is wrapped in a div with inline style
        songs = parse_chinese_cards(html)
        return songs
    
    for card in cards:
        song = _parse_single_card(card, html, is_chinese)
        if song:
            songs.append(song)
    
    return songs


def _parse_single_card(card, full_html, is_chinese=False):
    song = {'language': 'zh' if is_chinese else 'ja'}
    
    # Title
    title_match = re.search(r'class="famed-song-info"><b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', card)
    if not title_match:
        title_match = re.search(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', card)
        if title_match:
            song['title_jp'] = title_match.group(1)
            song['title_cn'] = title_match.group(1)
    else:
        song['title_cn'] = title_match.group(1)
        song['title_jp'] = title_match.group(2)
    
    if not song.get('title_jp'):
        return None
    
    # Producer (P主 or UP主)
    producer_match = re.search(r'<b>(?:P主|UP主)</b>.*?<a[^>]*>([^<]+)</a>', card)
    if not producer_match:
        return None
    song['producer'] = producer_match.group(1)
    
    # Date
    date_match = re.search(r'<b>投稿时间</b>[：:]\s*(\d{4}-\d{2}-\d{2})', card)
    if date_match:
        song['release_year'] = int(date_match.group(1)[:4])
    else:
        song['release_year'] = 0
    
    # Vocaloid - from famed-color or linear-gradient title
    vocaloid_match = re.search(r'(?:famed-color|linear-gradient)[^"]*"[^>]*title="([^"]+)"', card)
    if vocaloid_match:
        cn_name = vocaloid_match.group(1)
        song['vocaloid'] = VOCALOID_NAME_MAP.get(cn_name, cn_name)
    else:
        song['vocaloid'] = '洛天依' if is_chinese else '初音ミク'
    
    # Views
    song['nico_views'] = 1_500_000 if ('传说' in full_html) else 150_000
    
    return song


def parse_chinese_cards(html):
    """Parse Chinese VOCALOID song cards using position-based vocaloid matching"""
    songs = []
    
    # Find all vocaloid indicators and song entries by position
    vocaloid_matches = [(m.start(), m.group(1)) for m in re.finditer(r'linear-gradient[^\"]*\"[^>]*title=\"([^\"]+)\"', html)]
    song_matches = list(re.finditer(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', html))
    
    # For each song, find the closest preceding vocaloid indicator
    vi = 0
    for sm in song_matches:
        spos = sm.start()
        
        # Find vocaloid
        best_v = '洛天依'
        for vpos, vname in vocaloid_matches:
            if vpos < spos:
                best_v = vname
            else:
                break
        
        # Take first vocaloid if multiple (e.g. "洛天依、言和")
        best_v = best_v.split('、')[0].split('或')[0].strip()
        best_v = VOCALOID_NAME_MAP.get(best_v, best_v)
        
        # Get context for this song
        start = max(0, spos - 200)
        end = min(len(html), sm.end() + 300)
        chunk = html[start:end]
        
        song = {'language': 'zh', 'vocaloid': best_v, 'nico_views': 1_500_000}
        
        # Title
        title_match = re.search(r'<b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', chunk)
        if title_match:
            song['title_cn'] = title_match.group(1)
            song['title_jp'] = title_match.group(2)
        else:
            song['title_jp'] = sm.group(1)
            song['title_cn'] = sm.group(1)
        
        # Producer
        producer_match = re.search(r'<b>(?:P主|UP主)</b>：<a[^>]*>([^<]+)</a>', chunk)
        if not producer_match:
            continue
        song['producer'] = producer_match.group(1)
        
        # Date
        date_match = re.search(r'<b>投稿时间</b>[：:]\s*(\d{4}-\d{2}-\d{2})', chunk)
        if date_match:
            song['release_year'] = int(date_match.group(1)[:4])
        else:
            song['release_year'] = 0
        
        songs.append(song)
    
    return songs


def import_to_db(songs):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for song in songs:
        title = song.get('title_jp', '')
        title_cn = song.get('title_cn', '')
        producer = song.get('producer', '')
        year = song.get('release_year', 0)
        vocaloid = song.get('vocaloid', '初音ミク')
        language = song.get('language', 'ja')
        nico_views = song.get('nico_views', 150000)
        
        c.execute('SELECT id FROM songs WHERE title_jp = ? AND producer = ?', (title, producer))
        if c.fetchone():
            skipped += 1
            continue
        
        c.execute('''INSERT INTO songs 
            (title, title_jp, title_cn, producer, vocaloid, release_year, language, bpm, nico_views, genre, length_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, '', 0)''',
            (title, title, title_cn, producer, vocaloid, year, language, nico_views))
        inserted += 1
    
    conn.commit()
    conn.close()
    print(f"    Inserted: {inserted}, Duplicates skipped: {skipped}")
    return inserted


def main():
    total = 0
    
    print("=== VOCALOID传说曲 (Niconico) ===")
    html = fetch_page('https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2')
    if html:
        songs = parse_song_cards(html, is_chinese=False)
        print(f"  Parsed {len(songs)} songs")
        total += import_to_db(songs)
    time.sleep(1)
    
    print("\n=== VOCALOID传说曲/bilibili投稿 ===")
    html = fetch_page('https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2/bilibili%E6%8A%95%E7%A8%BF')
    if html:
        songs = parse_song_cards(html, is_chinese=False)
        print(f"  Parsed {len(songs)} songs")
        total += import_to_db(songs)
    time.sleep(1)
    
    print("\n=== VOCALOID中文传说曲 ===")
    html = fetch_page('https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E4%BC%A0%E8%AF%B4%E6%9B%B2')
    if html:
        songs = parse_song_cards(html, is_chinese=True)
        print(f"  Parsed {len(songs)} songs")
        total += import_to_db(songs)
    time.sleep(1)
    
    print("\n=== VOCALOID殿堂曲 ===")
    html = fetch_page('https://zh.moegirl.org.cn/VOCALOID%E6%AE%BF%E5%A0%82%E6%9B%B2')
    if html:
        songs = parse_song_cards(html, is_chinese=False)
        print(f"  Parsed {len(songs)} songs")
        total += import_to_db(songs)
    
    print(f"\n=== Done! Total new songs imported: {total} ===")


if __name__ == '__main__':
    main()