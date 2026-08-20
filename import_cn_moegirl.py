"""
Import Chinese VOCALOID songs from 萌娘百科 and enrich with bilibili durations.

Usage:
    python3 import_cn_moegirl.py
"""

import urllib.request, re, json, time, sqlite3

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
BILI_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}

VOC_MAP = {
    '洛天依': '洛天依', '言和': '言和', '乐正绫': '楽正綾', '乐正龙牙': '楽正龍牙',
    '心华': '心華', '星尘': '星尘', '初音未来': '初音ミク', '合唱或真人': '多人',
}

def parse_cn_page(url, views_tier):
    """Parse Chinese song entries from a Moegirl page."""
    req = urllib.request.Request(url, headers=HEADERS)
    html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
    
    voc_matches = [(m.start(), m.group(1)) for m in re.finditer(r'linear-gradient[^"]*"[^>]*title="([^"]+)"', html)]
    song_matches = list(re.finditer(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', html))
    
    songs = []
    for sm in song_matches:
        spos = sm.start()
        
        # Closest vocaloid indicator within 3000 chars
        best_voc = '洛天依'
        best_dist = 99999
        for vpos, vname in voc_matches:
            dist = abs(vpos - spos)
            if dist < best_dist and dist < 3000:
                best_dist = dist
                best_voc = vname
        best_voc = best_voc.split('、')[0].strip()
        best_voc = VOC_MAP.get(best_voc, best_voc)
        
        ctx = html[max(0, spos - 200):min(len(html), spos + 600)]
        
        # Title
        title_match = re.search(r'<b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', ctx)
        title_cn = title_match.group(1) if title_match else sm.group(1)
        title_jp = title_match.group(2) if title_match else sm.group(1)
        
        # Producer
        prod_match = re.search(r'<b>(?:UP主|P主)</b>[：:]<a[^>]*>([^<]+)</a>', ctx)
        if not prod_match:
            prod_match = re.search(r'(?:UP主|P主)[：:]<a[^>]*>([^<]+)</a>', ctx)
        if not prod_match:
            continue
        producer = prod_match.group(1)
        
        # Date
        date_match = re.search(r'<b>投稿时间</b>[：:]\s*(\d{4}-\d{2}-\d{2})', ctx)
        if not date_match:
            date_match = re.search(r'投稿时间[：:]\s*(\d{4}-\d{2}-\d{2})', ctx)
        year = int(date_match.group(1)[:4]) if date_match else 0
        
        # Bilibili avid
        avid = None
        avid_match = re.search(r'(?:data-bilibili-count-id="av|bilibili\.com/video/av)(\d+)', ctx)
        if avid_match:
            avid = avid_match.group(1)
        
        songs.append({
            'title_jp': title_jp, 'title_cn': title_cn,
            'producer': producer, 'release_year': year,
            'vocaloid': best_voc, 'language': 'zh',
            'nico_views': views_tier, 'bilibili_avid': avid,
        })
    
    return songs


def fetch_bilibili_duration(avid):
    """Get video duration from bilibili API."""
    try:
        url = f'https://api.bilibili.com/x/web-interface/view?aid={avid}'
        req = urllib.request.Request(url, headers=BILI_HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        if data['code'] == 0:
            return data['data']['duration']
    except Exception:
        pass
    return None


def main():
    conn = sqlite3.connect('songs.db')
    c = conn.cursor()
    
    # Parse pages
    print('=== 解析 VOCALOID中文传说曲 ===')
    legend = parse_cn_page('https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E4%BC%A0%E8%AF%B4%E6%9B%B2', 1500000)
    print(f'  解析到 {len(legend)} 首，{sum(1 for s in legend if s["bilibili_avid"])} 首有 B 站链接')
    
    time.sleep(1)
    
    print('=== 解析 VOCALOID中文殿堂曲 ===')
    hall = parse_cn_page('https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E6%AE%BF%E5%A0%82%E6%9B%B2', 150000)
    print(f'  解析到 {len(hall)} 首，{sum(1 for s in hall if s["bilibili_avid"])} 首有 B 站链接')
    
    all_songs = legend + hall
    
    # Import songs
    inserted = 0
    skipped = 0
    avid_map = {}
    
    for s in all_songs:
        # Check duplicate
        c.execute('SELECT id, length_sec FROM songs WHERE title_jp = ? AND producer = ?', (s['title_jp'], s['producer']))
        existing = c.fetchone()
        
        if existing:
            skipped += 1
            # Still map avid for duration update
            if s['bilibili_avid'] and existing[1] == 0:
                avid_map[existing[0]] = s['bilibili_avid']
            continue
        
        c.execute('''INSERT INTO songs (title, title_jp, title_cn, producer, vocaloid, release_year, language, bpm, nico_views, genre, length_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, "", 0)''',
            (s['title_jp'], s['title_jp'], s['title_cn'], s['producer'], s['vocaloid'], s['release_year'], s['language'], s['nico_views']))
        new_id = c.lastrowid
        inserted += 1
        
        if s['bilibili_avid']:
            avid_map[new_id] = s['bilibili_avid']
    
    conn.commit()
    print(f'\n导入完成：新增 {inserted}，重复跳过 {skipped}')
    
    # Fetch durations from bilibili
    print(f'\n=== 从 B 站 API 获取时长 ===')
    updated = 0
    
    # Sort: process all songs needing duration
    for song_id, avid in avid_map.items():
        dur = fetch_bilibili_duration(avid)
        if dur and dur > 0:
            c.execute('UPDATE songs SET length_sec = ? WHERE id = ? AND length_sec = 0', (dur, song_id))
            if c.rowcount > 0:
                updated += 1
                if updated <= 10:
                    c.execute('SELECT title_jp FROM songs WHERE id = ?', (song_id,))
                    row = c.fetchone()
                    print(f'  ✓ {row[0]} -> {dur}s ({dur//60}:{dur%60:02d})')
        time.sleep(0.3)
    
    conn.commit()
    
    # Stats
    c.execute('SELECT COUNT(*) FROM songs WHERE language = "zh"')
    cn_total = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM songs WHERE language = "zh" AND length_sec > 0')
    cn_with_len = c.fetchone()[0]
    
    print(f'\n完成！B 站时长更新 {updated} 首')
    print(f'中文曲：{cn_total} 首，其中 {cn_with_len} 首有时长')
    
    conn.close()


if __name__ == '__main__':
    main()
