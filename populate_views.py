# -*- coding: utf-8 -*-
"""Populate real play counts:
- zh/ACE songs: bilibili API stat.view (need bvid mapping from Moegirl pages)
- ja songs: niconico API view_counter via nico_sm_id
Then NULL out placeholder views that could not be verified.
"""
import urllib.request
import urllib.parse
import re
import sqlite3
import json
import time
import socket
import xml.etree.ElementTree as ET

socket.setdefaulttimeout(25)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
BILI_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}
DB = 'songs.db'

PAGES = [
    ('cn_legend', 'https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E4%BC%A0%E8%AF%B4%E6%9B%B2'),
    ('cn_hall_main', 'https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E6%AE%BF%E5%A0%82%E6%9B%B2'),
    ('ace_myth', 'https://zh.moegirl.org.cn/ACE%E7%A5%9E%E8%AF%9D%E6%9B%B2'),
    ('ace_legend', 'https://zh.moegirl.org.cn/ACE%E4%BC%A0%E8%AF%B4%E6%9B%B2'),
    ('ace_hall_main', 'https://zh.moegirl.org.cn/ACE%E6%AE%BF%E5%A0%82%E6%9B%B2'),
]


def fetch(url, timeout=60, headers=HEADERS):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8')
        except Exception as e:
            print('  retry', attempt, type(e).__name__, url[:80])
            time.sleep(4)
    return None


def parse_page(html):
    """Extract (title_cn, title_jp, producer, bvid, avid) from any card style."""
    out = []
    # song entries
    for m in re.finditer(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', html):
        ctx = html[max(0, m.start()-700):min(len(html), m.end()+600)]
        tm = re.search(r'<b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', ctx)
        tcn = tm.group(1) if tm else m.group(1)
        tjp = tm.group(2) if tm else m.group(1)
        pm = re.search(r'(?:<b>)?(?:UP主|P主)(?:</b>)?[：:]<a[^>]*>([^<]+)</a>', ctx)
        if not pm:
            continue
        producer = pm.group(1)
        bvm = re.search(r'(?:data-bilibili-count-id="|bilibili\.com/video/)(BV[0-9A-Za-z]+)', ctx)
        avm = re.search(r'(?:data-bilibili-count-id="av|bilibili\.com/video/av)(\d+)', ctx)
        out.append({
            'title_cn': tcn, 'title_jp': tjp, 'producer': producer,
            'bv': bvm.group(1) if bvm else None,
            'av': avm.group(1) if avm else None,
        })
    return out


def bili_info(bvid=None, avid=None):
    if not bvid and not avid:
        return None
    try:
        if bvid:
            url = 'https://api.bilibili.com/x/web-interface/view?bvid=' + bvid
        else:
            url = 'https://api.bilibili.com/x/web-interface/view?aid=' + str(avid)
        raw = fetch(url, headers=BILI_HEADERS, timeout=15)
        if not raw:
            return None
        data = json.loads(raw)
        if data.get('code') == 0:
            d = data['data']
            return {
                'duration': d.get('duration', 0),
                'views': (d.get('stat') or {}).get('view', 0),
                'pubdate': d.get('pubdate', 0),
            }
    except Exception:
        pass
    return None


def nico_views(sm_id):
    html = fetch('https://ext.nicovideo.jp/api/getthumbinfo/' + sm_id, timeout=15)
    if not html:
        return None
    try:
        root = ET.fromstring(html)
        if root.get('status') != 'ok':
            return None
        t = root.find('thumb')
        return int(t.find('view_counter').text)
    except Exception:
        return None


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ---- build bvid lookup from all zh/ace pages ----
    print('=== 解析页面构建 BV 映射 ===')
    urls = list(PAGES)
    for y in range(2012, 2027):
        urls.append((f'cn_hall_{y}', f'https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E6%AE%BF%E5%A0%82%E6%9B%B2/{y}%E5%B9%B4%E6%8A%95%E7%A8%BF'))
    for y in range(2022, 2027):
        urls.append((f'ace_hall_{y}', f'https://zh.moegirl.org.cn/ACE%E6%AE%BF%E5%A0%82%E6%9B%B2/{y}%E5%B9%B4%E6%8A%95%E7%A8%BF'))
    urls.append(('ace_hall_meme', 'https://zh.moegirl.org.cn/ACE%E6%AE%BF%E5%A0%82%E6%9B%B2/%E6%A2%97%E6%9B%B2%E7%9B%B8%E5%85%B3'))

    lookup = {}
    for label, url in urls:
        html = fetch(url)
        if not html:
            print(f'  {label}: FAILED')
            continue
        cards = parse_page(html)
        print(f'  {label}: {len(cards)} cards')
        for card in cards:
            for t in (card['title_cn'], card['title_jp']):
                key = (t.lower(), card['producer'].lower())
                if card['bv'] or card['av']:
                    if key not in lookup:
                        lookup[key] = (card['bv'], card['av'])
        time.sleep(0.8)

    print(f'BV 映射: {len(lookup)} 条')

    # ---- zh songs: bilibili ----
    print('\n=== 中文/ACE 曲目抓取 B 站真实播放量 ===')
    c.execute("SELECT id, title_jp, title_cn, producer, length_sec FROM songs WHERE language='zh'")
    zh_rows = c.fetchall()
    upd_views = 0
    upd_len = 0
    for i, (sid, title_jp, title_cn, producer, length_sec) in enumerate(zh_rows):
        key1 = ((title_cn or title_jp or '').lower(), producer.lower())
        key2 = ((title_jp or title_cn or '').lower(), producer.lower())
        bv, av = lookup.get(key1, (None, None))
        if not bv and not av:
            bv, av = lookup.get(key2, (None, None))
        if not bv and not av:
            continue
        info = bili_info(bvid=bv, avid=av)
        if not info:
            continue
        if info['views'] > 0:
            c.execute('UPDATE songs SET nico_views = ?, bvid = ? WHERE id = ?', (info['views'], bv, sid))
            upd_views += 1
        if info['duration'] > 0 and length_sec == 0:
            c.execute('UPDATE songs SET length_sec = ? WHERE id = ?', (info['duration'], sid))
            upd_len += 1
        if (i + 1) % 25 == 0:
            conn.commit()
            print(f'  zh 进度 {i+1}/{len(zh_rows)} (views {upd_views}, len {upd_len})')
        time.sleep(0.22)
    conn.commit()
    print(f'zh: 播放量更新 {upd_views}, 时长补 {upd_len}')

    # ---- ja songs: niconico via sm id ----
    print('\n=== 日文曲目抓取 Niconico 真实播放量 ===')
    c.execute("SELECT id, nico_sm_id FROM songs WHERE language='ja' AND nico_sm_id IS NOT NULL")
    ja_rows = c.fetchall()
    upd = 0
    for i, (sid, sm_id) in enumerate(ja_rows):
        v = nico_views(sm_id)
        if v and v > 0:
            c.execute('UPDATE songs SET nico_views = ? WHERE id = ?', (v, sid))
            upd += 1
        if (i + 1) % 30 == 0:
            conn.commit()
            print(f'  ja 进度 {i+1}/{len(ja_rows)} (更新 {upd})')
        time.sleep(0.3)
    conn.commit()
    print(f'ja: 播放量更新 {upd}')

    # ---- NULL out remaining placeholders (unverifiable) ----
    print('\n=== 清理无法核实的占位值 ===')
    c.execute("""UPDATE songs SET nico_views = NULL WHERE nico_views IN (150000, 1500000, 10000000)
        AND (language='zh' OR (language='ja' AND nico_sm_id IS NULL))""")
    n_null = c.rowcount
    conn.commit()
    print(f'置 NULL: {n_null}')

    c.execute('SELECT COUNT(*) FROM songs WHERE nico_views IS NULL')
    print('无播放量:', c.fetchone()[0])

    # stats
    c.execute("SELECT COUNT(*) FROM songs WHERE language='zh' AND nico_views > 0")
    print('中文有真实播放量:', c.fetchone()[0])
    c.execute("SELECT COUNT(*) FROM songs WHERE language='ja' AND nico_views > 0")
    print('日文有真实播放量:', c.fetchone()[0])
    conn.close()


if __name__ == '__main__':
    main()
