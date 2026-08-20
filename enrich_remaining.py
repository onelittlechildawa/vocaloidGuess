# -*- coding: utf-8 -*-
"""Fill remaining missing durations: ja via niconico/bilibili, zh via bilibili."""

import urllib.request
import urllib.parse
import re
import sqlite3
import json
import time
import socket
import xml.etree.ElementTree as ET

socket.setdefaulttimeout(20)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
BILI_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}
DB = 'songs.db'


def fetch(url, headers=HEADERS, timeout=20):
    try:
        req = urllib.request.Request(url, headers=headers)
        return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8')
    except Exception:
        return None


def parse_famed_cards(html):
    cards = re.findall(r'<div class="famed-song-card">(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
    out = []
    for card in cards:
        tm = re.search(r'class="famed-song-info"><b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', card)
        if tm:
            title_cn, title_jp = tm.group(1), tm.group(2)
        else:
            tm = re.search(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', card)
            if not tm:
                continue
            title_cn = title_jp = tm.group(1)
        pm = re.search(r'<b>P主</b>.*?<a[^>]*>([^<]+)</a>', card)
        if not pm:
            continue
        sm_m = re.search(r'nicovideo\.jp/watch/(sm\d+)', card)
        av_m = re.search(r'bilibili\.com/video/av(\d+)', card)
        bv_m = re.search(r'bilibili\.com/video/(BV[0-9A-Za-z]+)', card)
        out.append({
            'title_cn': title_cn, 'title_jp': title_jp, 'producer': pm.group(1),
            'sm': sm_m.group(1) if sm_m else None,
            'av': av_m.group(1) if av_m else None,
            'bv': bv_m.group(1) if bv_m else None,
        })
    return out


def parse_china_cards(html):
    out = []
    cards = re.findall(r'<div class="china-temple">(.*?)(?=<div class="china-temple">|<div class="Tab|<link rel|<style)', html, re.DOTALL)
    for card in cards:
        tm = re.search(r'<b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', card)
        if tm:
            title_cn, title_jp = tm.group(1), tm.group(2)
        else:
            tm = re.search(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', card)
            if not tm:
                continue
            title_cn = title_jp = tm.group(1)
        pm = re.search(r'(?:UP主|P主)[：:]<a[^>]*>([^<]+)</a>', card)
        if not pm:
            continue
        sm_m = re.search(r'nicovideo\.jp/watch/(sm\d+)', card)
        av_m = re.search(r'bilibili\.com/video/av(\d+)', card)
        bv_m = re.search(r'bilibili\.com/video/(BV[0-9A-Za-z]+)', card)
        out.append({
            'title_cn': title_cn, 'title_jp': title_jp, 'producer': pm.group(1),
            'sm': sm_m.group(1) if sm_m else None,
            'av': av_m.group(1) if av_m else None,
            'bv': bv_m.group(1) if bv_m else None,
        })
    return out


def nico_info(sm_id):
    if not sm_id:
        return None
    html = fetch('https://ext.nicovideo.jp/api/getthumbinfo/' + sm_id, timeout=15)
    if not html:
        return None
    try:
        root = ET.fromstring(html)
        if root.get('status') != 'ok':
            return None
        t = root.find('thumb')
        length = t.find('length').text.split(':')
        title = re.sub(r'^【[^】]*】', '', t.find('title').text).strip()
        return {
            'title': title,
            'length': int(length[0]) * 60 + int(length[1]),
            'views': int(t.find('view_counter').text),
            'year': int(t.find('first_retrieve').text[:4]),
        }
    except Exception:
        return None


def bili_info(bvid=None, avid=None):
    if not bvid and not avid:
        return None
    try:
        if bvid:
            url = 'https://api.bilibili.com/x/web-interface/view?bvid=' + bvid
        else:
            url = 'https://api.bilibili.com/x/web-interface/view?aid=' + str(avid)
        raw = fetch(url, headers=BILI_HEADERS, timeout=12)
        if not raw:
            return None
        data = json.loads(raw)
        if data.get('code') == 0:
            d = data['data']
            return {'length': d['duration'], 'title': d.get('title', '')}
    except Exception:
        pass
    return None


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    print('=== parse pages ===')
    pages = [
        ('nico legend', 'https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2', 'famed'),
        ('bili posts', 'https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2/bilibili%E6%8A%95%E7%A8%BF', 'famed'),
        ('nico hall', 'https://zh.moegirl.org.cn/VOCALOID%E6%AE%BF%E5%A0%82%E6%9B%B2', 'famed'),
        ('cn legend', 'https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E4%BC%A0%E8%AF%B4%E6%9B%B2', 'china'),
        ('cn hall', 'https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E6%AE%BF%E5%A0%82%E6%9B%B2', 'china'),
    ]
    lookup = {}
    for name, url, style in pages:
        html = fetch(url, timeout=60)
        if not html:
            print('  ' + name + ': fetch failed')
            continue
        cards = parse_famed_cards(html) if style == 'famed' else parse_china_cards(html)
        print('  ' + name + ': ' + str(len(cards)) + ' cards')
        for card in cards:
            for t in (card['title_cn'], card['title_jp']):
                key = (t.lower(), card['producer'].lower())
                if key not in lookup:
                    lookup[key] = card
        time.sleep(1)

    print('lookup: ' + str(len(lookup)))

    print('\n=== ja ===')
    c.execute("SELECT id, title_jp, title_cn, producer, nico_sm_id FROM songs WHERE length_sec = 0 AND language = 'ja'")
    ja_rows = c.fetchall()
    ja_upd = 0
    for i, (sid, title_jp, title_cn, producer, sm_id) in enumerate(ja_rows):
        key1 = ((title_cn or title_jp or '').lower(), producer.lower())
        key2 = ((title_jp or title_cn or '').lower(), producer.lower())
        card = lookup.get(key1) or lookup.get(key2)

        info = None
        source = ''

        if sm_id:
            info = nico_info(sm_id)
            source = 'nico-db'
        if not info and card and card['sm']:
            info = nico_info(card['sm'])
            source = 'nico-card'
            if info:
                c.execute('UPDATE songs SET nico_sm_id = ? WHERE id = ?', (card['sm'], sid))
        if not info and card and (card['bv'] or card['av']):
            info = bili_info(card['bv'], card['av'])
            source = 'bili-card'
        if not info and title_cn:
            art_html = fetch('https://zh.moegirl.org.cn/' + urllib.parse.quote(title_cn), timeout=20)
            if art_html:
                m = re.search(r'nicovideo\.jp/watch/(sm\d+)', art_html)
                if m:
                    info = nico_info(m.group(1))
                    source = 'nico-article'
                    if info:
                        c.execute('UPDATE songs SET nico_sm_id = ? WHERE id = ?', (m.group(1), sid))
                else:
                    m2 = re.search(r'bilibili\.com/video/av(\d+)', art_html)
                    m3 = re.search(r'bilibili\.com/video/(BV[0-9A-Za-z]+)', art_html)
                    if m2 or m3:
                        info = bili_info(avid=m2.group(1) if m2 else None, bvid=m3.group(1) if m3 else None)
                        source = 'bili-article'

        if info and info.get('length', 0) > 0:
            if source.startswith('nico'):
                c.execute('''UPDATE songs SET title_jp = ?, title = ?, length_sec = ?, nico_views = ?,
                    release_year = CASE WHEN release_year = 0 THEN ? ELSE release_year END WHERE id = ?''',
                    (info['title'], info['title'], info['length'], info['views'], info['year'], sid))
            else:
                c.execute('UPDATE songs SET length_sec = ? WHERE id = ?', (info['length'], sid))
            ja_upd += 1
            if ja_upd <= 20 or ja_upd % 50 == 0:
                print('  OK [' + source + '] ' + (title_jp or '')[:30] + ' -> ' + str(info['length']) + 's (' + str(ja_upd) + '/' + str(len(ja_rows)) + ')')

        if (i + 1) % 15 == 0:
            conn.commit()
        time.sleep(0.25)

    conn.commit()
    print('ja updated: ' + str(ja_upd))

    print('\n=== zh ===')
    c.execute("SELECT id, title_jp, title_cn, producer FROM songs WHERE length_sec = 0 AND language = 'zh'")
    zh_rows = c.fetchall()
    zh_upd = 0
    for i, (sid, title_jp, title_cn, producer) in enumerate(zh_rows):
        key1 = ((title_cn or title_jp or '').lower(), producer.lower())
        key2 = ((title_jp or title_cn or '').lower(), producer.lower())
        card = lookup.get(key1) or lookup.get(key2)

        info = None
        if card and (card['bv'] or card['av']):
            info = bili_info(card['bv'], card['av'])
        if not info and title_cn:
            art_html = fetch('https://zh.moegirl.org.cn/' + urllib.parse.quote(title_cn), timeout=20)
            if art_html:
                m2 = re.search(r'bilibili\.com/video/av(\d+)', art_html)
                m3 = re.search(r'bilibili\.com/video/(BV[0-9A-Za-z]+)', art_html)
                if m2 or m3:
                    info = bili_info(avid=m2.group(1) if m2 else None, bvid=m3.group(1) if m3 else None)

        if info and info.get('length', 0) > 0:
            c.execute('UPDATE songs SET length_sec = ? WHERE id = ?', (info['length'], sid))
            zh_upd += 1
            if zh_upd <= 20 or zh_upd % 50 == 0:
                print('  OK ' + (title_jp or '')[:30] + ' -> ' + str(info['length']) + 's (' + str(zh_upd) + '/' + str(len(zh_rows)) + ')')

        if (i + 1) % 15 == 0:
            conn.commit()
        time.sleep(0.25)

    conn.commit()
    print('zh updated: ' + str(zh_upd))

    c.execute('SELECT COUNT(*) FROM songs WHERE length_sec > 0')
    with_len = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM songs')
    total = c.fetchone()[0]
    print('\ncoverage: ' + str(with_len) + '/' + str(total) + ' (' + str(100 * with_len // total) + '%)')
    conn.close()


if __name__ == '__main__':
    main()
