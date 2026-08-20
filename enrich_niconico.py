"""
Enrich Japanese songs from Moegirl using Niconico API.

1. Re-parse Moegirl pages (传说曲/殿堂曲/bilibili投稿), extracting niconico sm id per card.
2. Query https://ext.nicovideo.jp/api/getthumbinfo/smXXXX for:
   - Japanese title
   - length (duration)
   - actual view counter
   - first retrieve date
3. Update songs.db.

Usage:
    python3 enrich_niconico.py
"""

import urllib.request
import urllib.parse
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
import sys

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
DB = 'songs.db'

PAGES = [
    ('https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2', 1_500_000),
    ('https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2/bilibili%E6%8A%95%E7%A8%BF', 1_500_000),
    ('https://zh.moegirl.org.cn/VOCALOID%E6%AE%BF%E5%A0%82%E6%9B%B2', 150_000),
]


def parse_moegirl_cards(url, views_tier):
    """Parse song cards, return list of dicts with sm id."""
    req = urllib.request.Request(url, headers=HEADERS)
    html = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')

    # Split into cards
    cards = re.findall(r'<div class="famed-song-card">(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
    results = []

    for card in cards:
        # Title: <a title="CN">JP</a>
        title_match = re.search(r'class="famed-song-info"><b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', card)
        if title_match:
            title_cn = title_match.group(1)
            title_jp = title_match.group(2)
        else:
            title_match = re.search(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', card)
            if not title_match:
                continue
            title_cn = title_match.group(1)
            title_jp = title_match.group(1)

        # Producer
        prod_match = re.search(r'<b>P主</b>.*?<a[^>]*>([^<]+)</a>', card)
        if not prod_match:
            continue
        producer = prod_match.group(1)

        # Date
        date_match = re.search(r'<b>投稿时间</b>[：:]\s*(\d{4}-\d{2}-\d{2})', card)
        year = int(date_match.group(1)[:4]) if date_match else 0

        # Vocaloid
        voc_match = re.search(r'famed-color[^"]*"[^>]*title="([^"]+)"', card)
        vocaloid = voc_match.group(1) if voc_match else '初音ミク'

        # Niconico sm id
        sm_match = re.search(r'nicovideo\.jp/watch/(sm\d+)', card)
        sm_id = sm_match.group(1) if sm_match else None

        results.append({
            'title_cn': title_cn,
            'title_jp': title_jp,
            'producer': producer,
            'release_year': year,
            'vocaloid': vocaloid,
            'nico_views': views_tier,
            'sm_id': sm_id,
        })

    return results


def fetch_niconico_info(sm_id):
    """Query Niconico getthumbinfo API."""
    url = f'https://ext.nicovideo.jp/api/getthumbinfo/{sm_id}'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read().decode('utf-8')
        root = ET.fromstring(data)
        if root.get('status') != 'ok':
            return None
        thumb = root.find('thumb')
        if thumb is None:
            return None

        def get_text(tag):
            el = thumb.find(tag)
            return el.text if el is not None else None

        length_str = get_text('length') or '0:00'  # format mm:ss
        parts = length_str.split(':')
        length_sec = int(parts[0]) * 60 + int(parts[1])

        view_counter = get_text('view_counter')
        views = int(view_counter) if view_counter else 0

        first_retrieve = get_text('first_retrieve')
        year = int(first_retrieve[:4]) if first_retrieve else 0

        return {
            'title_jp': get_text('title') or '',
            'length_sec': length_sec,
            'views': views,
            'year': year,
        }
    except Exception:
        return None


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    print('=== 解析萌娘百科页面 ===')
    all_cards = []
    for url, tier in PAGES:
        try:
            cards = parse_moegirl_cards(url, tier)
            print(f'  {url.split("/")[-1]}: {len(cards)} cards')
            all_cards.extend(cards)
        except Exception as e:
            print(f'  {url}: ERROR {e}')
        time.sleep(1)

    # Build lookup: (title_cn, producer) -> sm_id
    sm_lookup = {}
    for card in all_cards:
        if card['sm_id']:
            key = (card['title_cn'].lower(), card['producer'].lower())
            sm_lookup[key] = card['sm_id']

    # Also match by title_jp
    for card in all_cards:
        if card['sm_id']:
            key = (card['title_jp'].lower(), card['producer'].lower())
            if key not in sm_lookup:
                sm_lookup[key] = card['sm_id']

    print(f'\n共 {len(sm_lookup)} 个 sm id 映射')

    # Find songs to update
    c.execute("SELECT id, title, title_jp, title_cn, producer, release_year FROM songs WHERE language = 'ja'")
    ja_songs = c.fetchall()

    matched = 0
    unmatched = 0
    for song in ja_songs:
        sid, title, title_jp, title_cn, producer, year = song
        key = ((title_cn or title_jp or title).lower(), producer.lower())
        sm_id = sm_lookup.get(key)
        if not sm_id:
            key2 = ((title_jp or title).lower(), producer.lower())
            sm_id = sm_lookup.get(key2)

        if sm_id:
            matched += 1
            c.execute('UPDATE songs SET nico_sm_id = ? WHERE id = ?', (sm_id, sid))
        else:
            unmatched += 1

    conn.commit()
    print(f'匹配: {matched}, 未匹配: {unmatched}')

    # Now fetch Niconico data for matched songs
    print('\n=== 查询 Niconico API ===')
    c.execute("SELECT id, title_jp, nico_sm_id FROM songs WHERE nico_sm_id IS NOT NULL AND length_sec = 0")
    to_fetch = c.fetchall()
    print(f'需要查询: {len(to_fetch)} 首')

    updated = 0
    failed = 0
    for i, (sid, old_title, sm_id) in enumerate(to_fetch):
        info = fetch_niconico_info(sm_id)
        if info and info['length_sec'] > 0:
            # Clean title: remove 【vocaloid】 markers
            clean_title = re.sub(r'^【[^】]*】', '', info['title_jp']).strip()
            c.execute('''UPDATE songs 
                SET title_jp = ?, title = ?, length_sec = ?, nico_views = ?, release_year = CASE WHEN release_year = 0 THEN ? ELSE release_year END
                WHERE id = ?''',
                (clean_title, clean_title, info['length_sec'], info['views'], info['year'], sid))
            updated += 1
            if updated <= 10:
                print(f'  ✓ [{sm_id}] {clean_title[:40]} -> {info["length_sec"]}s, {info["views"]} views')
        else:
            failed += 1

        if (i + 1) % 20 == 0:
            print(f'  进度: {i+1}/{len(to_fetch)} (更新 {updated}, 失败 {failed})')
            conn.commit()

        time.sleep(0.4)

    conn.commit()
    print(f'\n完成! 更新: {updated}, 失败: {failed}')

    # Final stats
    c.execute('SELECT COUNT(*) FROM songs WHERE length_sec > 0')
    with_len = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM songs')
    total = c.fetchone()[0]
    print(f'时长覆盖: {with_len}/{total} ({100*with_len//total}%)')
    conn.close()


if __name__ == '__main__':
    main()
