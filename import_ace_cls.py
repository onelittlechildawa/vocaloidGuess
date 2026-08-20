# -*- coding: utf-8 -*-
"""Import ACE神话曲 / ACE传说曲 (CLS template pages)."""

import urllib.request
import re
import sqlite3
import json
import time
import socket

socket.setdefaulttimeout(25)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
BILI_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}
DB = 'songs.db'


def fetch(url, timeout=60):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8')
        except Exception as e:
            print('  retry', attempt, type(e).__name__)
            time.sleep(4)
    return None


def parse_cls_page(html):
    """Parse CLS-template cards: vocaloid gradient markers + song entries."""
    vocs = [(m.start(), m.group(1)) for m in re.finditer(r'linear-gradient[^"]*"[^>]*title="([^"]+)"', html)]
    songs = []
    for m in re.finditer(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', html):
        spos = m.start()
        best = '多人'
        for vpos, vname in vocs:
            if vpos < spos:
                best = vname
            else:
                break
        best = best.split('、')[0].strip()

        ctx = html[max(0, spos - 500):min(len(html), m.end() + 500)]
        tm = re.search(r'<b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', ctx)
        tcn = tm.group(1) if tm else m.group(1)
        tjp = tm.group(2) if tm else m.group(1)

        pm = re.search(r'<b>(?:UP主|P主)</b>[：:]<a[^>]*>([^<]+)</a>', ctx)
        if not pm:
            pm = re.search(r'(?:UP主|P主)[：:]<a[^>]*>([^<]+)</a>', ctx)
        if not pm:
            continue
        producer = pm.group(1)

        dm = re.search(r'<b>投稿时间</b>[：:]\s*(\d{4}-\d{2}-\d{2})', ctx)
        if not dm:
            dm = re.search(r'投稿时间[：:]\s*(\d{4}-\d{2}-\d{2})', ctx)
        year = int(dm.group(1)[:4]) if dm else 0

        bvm = re.search(r'(?:data-bilibili-count-id="|bilibili\.com/video/)(BV[0-9A-Za-z]+)', ctx)
        if not bvm:
            bvm = re.search(r'data-bilibili-count-id="(BV[0-9A-Za-z]+)"', ctx)
        avm = re.search(r'(?:data-bilibili-count-id="av|bilibili\.com/video/av)(\d+)', ctx)

        songs.append({
            'title_cn': tcn, 'title_jp': tjp, 'producer': producer,
            'release_year': year, 'vocaloid': best,
            'bv': bvm.group(1) if bvm else None,
            'av': avm.group(1) if avm else None,
        })
    return songs


def bili_duration(bvid=None, avid=None):
    if not bvid and not avid:
        return None
    try:
        if bvid:
            url = 'https://api.bilibili.com/x/web-interface/view?bvid=' + bvid
        else:
            url = 'https://api.bilibili.com/x/web-interface/view?aid=' + str(avid)
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=BILI_HEADERS), timeout=15).read().decode('utf-8')
        data = json.loads(raw)
        if data.get('code') == 0:
            return data['data']['duration']
    except Exception:
        pass
    return None


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    pages = [
        ('ACE神话曲', 'https://zh.moegirl.org.cn/ACE%E7%A5%9E%E8%AF%9D%E6%9B%B2', '神话', 10_000_000),
        ('ACE传说曲', 'https://zh.moegirl.org.cn/ACE%E4%BC%A0%E8%AF%B4%E6%9B%B2', '传说', 1_500_000),
    ]

    all_songs = []
    seen = set()
    for label, url, tier, views in pages:
        html = fetch(url)
        if not html:
            print(f'{label}: FAILED')
            continue
        songs = parse_cls_page(html)
        print(f'{label}: {len(songs)}')
        for s in songs:
            key = (s['title_cn'].lower(), s['producer'].lower())
            if key in seen:
                continue
            seen.add(key)
            s['tier'] = tier
            s['views'] = views
            all_songs.append(s)
        time.sleep(1.5)

    print(f'去重后 {len(all_songs)} 首')

    inserted = 0
    existed = 0
    need_dur = []
    for s in all_songs:
        c.execute('''SELECT id, length_sec, tier FROM songs WHERE producer = ? AND (
            title_cn = ? OR title_jp = ? OR title = ?)''',
            (s['producer'], s['title_cn'], s['title_cn'], s['title_cn']))
        row = c.fetchone()
        if row:
            existed += 1
            sid = row[0]
            tier_rank = {'殿堂': 1, '传说': 2, '神话': 3}
            if tier_rank.get(s['tier'], 0) > tier_rank.get(row[2] or '', 0):
                c.execute('UPDATE songs SET tier = ? WHERE id = ?', (s['tier'], sid))
            c.execute("UPDATE songs SET engine = COALESCE(engine, 'ACE') WHERE id = ?", (sid,))
            if row[1] == 0 and (s['av'] or s['bv']):
                need_dur.append((sid, s['bv'], s['av']))
            continue
        c.execute('''INSERT INTO songs (title, title_jp, title_cn, producer, vocaloid, release_year, language, bpm, nico_views, tier, genre, length_sec, engine)
            VALUES (?, ?, ?, ?, ?, ?, 'zh', 0, ?, ?, '', 0, 'ACE')''',
            (s['title_jp'], s['title_jp'], s['title_cn'], s['producer'], s['vocaloid'],
             s['release_year'], s['views'], s['tier']))
        inserted += 1
        if s['av'] or s['bv']:
            need_dur.append((c.lastrowid, s['bv'], s['av']))

    conn.commit()
    print(f'新增 {inserted}，已存在 {existed}')

    print('=== bilibili 时长 ===')
    upd = 0
    for i, (sid, bvid, avid) in enumerate(need_dur):
        dur = bili_duration(bvid, avid)
        if dur and dur > 0:
            c.execute('UPDATE songs SET length_sec = ? WHERE id = ? AND length_sec = 0', (dur, sid))
            if c.rowcount:
                upd += 1
                if upd <= 15 or upd % 100 == 0:
                    c.execute('SELECT title_jp FROM songs WHERE id = ?', (sid,))
                    r = c.fetchone()
                    print(f'  OK {r[0][:30]} -> {dur}s ({upd})')
        if (i + 1) % 25 == 0:
            conn.commit()
        time.sleep(0.25)

    conn.commit()
    print(f'时长更新: {upd}')

    c.execute("SELECT COUNT(*) FROM songs WHERE engine = 'ACE'")
    ace_total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE engine = 'ACE' AND length_sec > 0")
    ace_len = c.fetchone()[0]
    c.execute("SELECT tier, COUNT(*) FROM songs WHERE engine = 'ACE' GROUP BY tier")
    print(f'\nACE 入库: {ace_total} 首，时长 {ace_len}')
    for r in c.fetchall():
        print(f'  {r[0]}: {r[1]}')
    conn.close()


if __name__ == '__main__':
    main()
