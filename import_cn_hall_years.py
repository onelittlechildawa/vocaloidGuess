# -*- coding: utf-8 -*-
"""Import Chinese 殿堂曲 from all year subpages of 萌娘百科 + bilibili durations."""
import urllib.request
import urllib.parse
import re
import sqlite3
import json
import time
import socket

socket.setdefaulttimeout(25)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
BILI_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}
DB = 'songs.db'

VOC_MAP = {
    '洛天依': '洛天依', '言和': '言和', '乐正绫': '楽正綾', '乐正龙牙': '楽正龍牙',
    '心华': '心華', '星尘': '星尘', '初音未来': '初音ミク', '合唱或真人': '多人',
    '镜音铃': '鏡音リン', '镜音连': '鏡音レン', '巡音流歌': '巡音ルカ', 'GUMI': 'GUMI',
}


def fetch(url, timeout=60):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8')
        except Exception as e:
            print('  retry', attempt, type(e).__name__)
            time.sleep(4)
    return None


def parse_china_page(html):
    """Parse china-temple cards. Returns list of dicts."""
    songs = []
    # vocaloid indicators
    vocs = [(m.start(), m.group(1)) for m in re.finditer(r'linear-gradient[^"]*"[^>]*title="([^"]+)"', html)]
    for m in re.finditer(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', html):
        spos = m.start()
        # nearest preceding vocaloid
        best = '洛天依'
        for vpos, vname in vocs:
            if vpos < spos:
                best = vname
            else:
                break
        best = best.split('、')[0].split('或')[0].strip()
        best = VOC_MAP.get(best, best)

        ctx = html[max(0, spos - 300):min(len(html), m.end() + 600)]
        tm = re.search(r'<b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', ctx)
        tcn = tm.group(1) if tm else m.group(1)
        tjp = tm.group(2) if tm else m.group(1)

        pm = re.search(r'(?:UP主|P主)[：:]<a[^>]*>([^<]+)</a>', ctx)
        if not pm:
            continue
        producer = pm.group(1)

        dm = re.search(r'投稿时间[：:]\s*(\d{4}-\d{2}-\d{2})', ctx)
        year = int(dm.group(1)[:4]) if dm else 0

        avm = re.search(r'(?:data-bilibili-count-id="av|bilibili\.com/video/av)(\d+)', ctx)
        bvm = re.search(r'bilibili\.com/video/(BV[0-9A-Za-z]+)', ctx)
        smm = re.search(r'nicovideo\.jp/watch/(sm\d+)', ctx)

        songs.append({
            'title_cn': tcn, 'title_jp': tjp, 'producer': producer,
            'release_year': year, 'vocaloid': best,
            'av': avm.group(1) if avm else None,
            'bv': bvm.group(1) if bvm else None,
            'sm': smm.group(1) if smm else None,
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
        req = urllib.request.Request(url, headers=BILI_HEADERS)
        raw = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
        data = json.loads(raw)
        if data.get('code') == 0:
            return data['data']['duration']
    except Exception:
        pass
    return None


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    urls = [
        ('主页面', 'https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E6%AE%BF%E5%A0%82%E6%9B%B2'),
    ]
    for y in range(2012, 2027):
        urls.append((f'{y}年', f'https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E6%AE%BF%E5%A0%82%E6%9B%B2/{y}%E5%B9%B4%E6%8A%95%E7%A8%BF'))

    all_songs = []
    seen = set()
    for label, url in urls:
        html = fetch(url)
        if not html:
            print(f'{label}: FAILED')
            continue
        songs = parse_china_page(html)
        print(f'{label}: {len(songs)} 首')
        for s in songs:
            key = (s['title_cn'].lower(), s['producer'].lower())
            if key in seen:
                continue
            seen.add(key)
            all_songs.append(s)
        time.sleep(1.5)

    print(f'去重后共 {len(all_songs)} 首')

    # import
    inserted = 0
    existed = 0
    need_dur = []
    for s in all_songs:
        # match existing by any title + producer
        c.execute("""SELECT id, length_sec FROM songs WHERE producer = ? AND (
            title = ? OR title_jp = ? OR title_cn = ? OR
            title = ? OR title_jp = ? OR title_cn = ?)""",
            (s['producer'], s['title_cn'], s['title_cn'], s['title_cn'],
             s['title_jp'], s['title_jp'], s['title_jp']))
        row = c.fetchone()
        if row:
            existed += 1
            sid = row[0]
            if row[1] == 0 and (s['av'] or s['bv']):
                need_dur.append((sid, s['bv'], s['av']))
            # ensure tier 殿堂
            c.execute("UPDATE songs SET tier = '殿堂' WHERE id = ? AND tier != '传说'", (sid,))
            continue
        c.execute('''INSERT INTO songs (title, title_jp, title_cn, producer, vocaloid, release_year, language, bpm, nico_views, tier, genre, length_sec)
            VALUES (?, ?, ?, ?, ?, ?, 'zh', 0, 150000, '殿堂', '', 0)''',
            (s['title_jp'], s['title_jp'], s['title_cn'], s['producer'], s['vocaloid'], s['release_year']))
        sid = c.lastrowid
        inserted += 1
        if s['av'] or s['bv']:
            need_dur.append((sid, s['bv'], s['av']))

    conn.commit()
    print(f'新增 {inserted}，已存在 {existed}')

    # durations
    print('=== bilibili 时长 ===')
    upd = 0
    for i, (sid, bvid, avid) in enumerate(need_dur):
        dur = bili_duration(bvid, avid)
        if dur and dur > 0:
            c.execute('UPDATE songs SET length_sec = ? WHERE id = ? AND length_sec = 0', (dur, sid))
            if c.rowcount:
                upd += 1
                if upd <= 20 or upd % 100 == 0:
                    c.execute('SELECT title_jp FROM songs WHERE id = ?', (sid,))
                    r = c.fetchone()
                    print(f'  OK {r[0][:30]} -> {dur}s ({upd})')
        if (i + 1) % 20 == 0:
            conn.commit()
        time.sleep(0.3)

    conn.commit()
    print(f'时长更新: {upd}')

    c.execute("SELECT COUNT(*) FROM songs WHERE language='zh'")
    cn = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE language='zh' AND tier='殿堂'")
    hall = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE language='zh' AND tier='传说'")
    leg = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM songs WHERE language='zh' AND length_sec > 0")
    cnl = c.fetchone()[0]
    print(f'\n中文曲: {cn} (传说 {leg} / 殿堂 {hall})，时长 {cnl}')
    conn.close()


if __name__ == '__main__':
    main()
