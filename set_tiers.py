# -*- coding: utf-8 -*-
"""Set tier (传说/殿堂/人气/普通) per Moegirl page classification."""
import urllib.request
import urllib.parse
import re
import sqlite3
import time

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

PAGES = [
    ('https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2', 'famed', '传说'),
    ('https://zh.moegirl.org.cn/VOCALOID%E4%BC%A0%E8%AF%B4%E6%9B%B2/bilibili%E6%8A%95%E7%A8%BF', 'famed', '传说'),
    ('https://zh.moegirl.org.cn/VOCALOID%E6%AE%BF%E5%A0%82%E6%9B%B2', 'famed', '殿堂'),
    ('https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E4%BC%A0%E8%AF%B4%E6%9B%B2', 'china', '传说'),
    ('https://zh.moegirl.org.cn/VOCALOID%E4%B8%AD%E6%96%87%E6%AE%BF%E5%A0%82%E6%9B%B2', 'china', '殿堂'),
]

def fetch(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        return urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    except Exception:
        return None

def famed_cards(html):
    cards = re.findall(r'<div class="famed-song-card">(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
    out = []
    for card in cards:
        tm = re.search(r'class="famed-song-info"><b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', card)
        if tm:
            tcn, tjp = tm.group(1), tm.group(2)
        else:
            tm = re.search(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', card)
            if not tm:
                continue
            tcn = tjp = tm.group(1)
        pm = re.search(r'<b>P主</b>.*?<a[^>]*>([^<]+)</a>', card)
        if not pm:
            continue
        out.append((tcn, tjp, pm.group(1)))
    return out

def china_cards(html):
    # song entries + nearest preceding vocaloid gradient (producer near song entry)
    out = []
    for m in re.finditer(r'<b>曲目</b>：<a[^>]*>([^<]+)</a>', html):
        ctx = html[max(0, m.start()-800):min(len(html), m.end()+600)]
        tm = re.search(r'<b>曲目</b>：<a[^>]*title="([^"]*)"[^>]*>([^<]+)</a>', ctx)
        tcn = tm.group(1) if tm else m.group(1)
        tjp = tm.group(2) if tm else m.group(1)
        pm = re.search(r'(?:UP主|P主)</?b?>[：:]<a[^>]*>([^<]+)</a>', ctx)
        if not pm:
            continue
        out.append((tcn, tjp, pm.group(1)))
    return out

def main():
    conn = sqlite3.connect('songs.db')
    c = conn.cursor()

    pairs = []  # (title_cn, title_jp, producer, tier)
    for url, style, tier in PAGES:
        html = fetch(url)
        if not html:
            print('fetch failed:', url)
            continue
        cards = famed_cards(html) if style == 'famed' else china_cards(html)
        print('%-30s %d cards -> %s' % (url.split('/')[-1][:30], len(cards), tier))
        for tcn, tjp, prod in cards:
            pairs.append((tcn, tjp, prod, tier))
        time.sleep(3)

    updated = 0
    for tcn, tjp, prod, tier in pairs:
        for title in (tcn, tjp):
            c.execute('UPDATE songs SET tier = ? WHERE (title_cn = ? OR title_jp = ? OR title = ?) AND producer = ? AND tier IS NULL',
                      (tier, title, title, title, prod))
            if c.rowcount > 0:
                updated += 1

    # Remaining: derive from views
    c.execute('''UPDATE songs SET tier = '传说' WHERE tier IS NULL AND nico_views >= 10000000''')
    c.execute('''UPDATE songs SET tier = '殿堂' WHERE tier IS NULL AND nico_views >= 1000000''')
    c.execute('''UPDATE songs SET tier = '人气' WHERE tier IS NULL AND nico_views >= 100000''')
    c.execute('''UPDATE songs SET tier = '普通' WHERE tier IS NULL''')

    conn.commit()

    c.execute('SELECT tier, COUNT(*) FROM songs GROUP BY tier')
    print('\ntier distribution:')
    for row in c.fetchall():
        print('  %s: %d' % row)
    conn.close()


if __name__ == '__main__':
    main()
