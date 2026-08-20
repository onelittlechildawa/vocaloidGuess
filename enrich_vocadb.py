"""
Enrich song database with VocaDB data (length, voicebank, accurate dates)

Usage:
    python3 enrich_vocadb.py          # Enrich all songs missing length
    python3 enrich_vocadb.py --limit 50  # Only process 50 songs
"""

import urllib.request, urllib.parse, json, time, sys, re
from database import get_db
from difflib import SequenceMatcher

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Origin': 'https://vocadb.net',
    'Referer': 'https://vocadb.net/',
}

def search_vocadb(title, producer=None):
    """Search VocaDB by title, return best matches"""
    # Try English title first (romaji)
    query = urllib.parse.quote(title)
    url = f'https://vocadb.net/api/songs?query={query}&maxResults=10&fields=AdditionalNames,Artists&lang=English'
    
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        return data.get('items', [])
    except Exception as e:
        print(f'    VocaDB error: {e}')
        return []

def similarity(a, b):
    """Calculate string similarity"""
    if not a or not b:
        return 0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(items, title, producer):
    """Find the best matching song from VocaDB results"""
    best = None
    best_score = 0
    
    for item in items:
        item_title = item.get('defaultName', '')
        item_artist = item.get('artistString', '')
        
        # Score based on title similarity and producer match
        title_score = similarity(title, item_title)
        
        # Also check additional names
        for alt_name in item.get('additionalNames', '').split(','):
            alt_name = alt_name.strip()
            if alt_name:
                title_score = max(title_score, similarity(title, alt_name))
        
        producer_score = 0
        if producer and producer.lower() in item_artist.lower():
            producer_score = 0.5
        
        # Prefer original versions (no originalVersionId)
        is_original = not item.get('originalVersionId')
        originality_bonus = 0.2 if is_original else 0
        
        total_score = title_score * 0.5 + producer_score + originality_bonus
        
        if total_score > best_score:
            best_score = total_score
            best = item
    
    if best_score >= 0.5:
        return best
    return None

def extract_voicebank(artist_string):
    """Extract voicebank info from VocaDB artist string"""
    # Pattern: "Producer feat. Vocaloid (Voicebank)"
    match = re.search(r'feat\.\s*(.+)$', artist_string)
    if match:
        return match.group(1).strip()
    return artist_string

def enrich_database(limit=None):
    """Enrich songs with missing length data from VocaDB"""
    conn = get_db()
    c = conn.cursor()
    
    # Get songs missing length
    c.execute('SELECT id, title, title_jp, producer, release_year FROM songs WHERE length_sec = 0 ORDER BY nico_views DESC')
    rows = c.fetchall()
    
    if limit:
        rows = rows[:limit]
    
    print(f'Found {len(rows)} songs to enrich')
    
    updated = 0
    failed = 0
    
    for i, row in enumerate(rows):
        title = row['title'] or row['title_jp']
        producer = row['producer']
        
        if i % 10 == 0:
            print(f'  Progress: {i}/{len(rows)} (updated: {updated}, failed: {failed})')
        
        # Search VocaDB
        items = search_vocadb(title, producer)
        
        if not items:
            # Try Japanese title
            if row['title_jp'] and row['title_jp'] != row['title']:
                items = search_vocadb(row['title_jp'], producer)
        
        if items:
            best = find_best_match(items, title, producer)
            if best:
                length = best.get('lengthSeconds', 0)
                publish_date = best.get('publishDate', '')
                artist_string = best.get('artistString', '')
                voicebank = extract_voicebank(artist_string)
                
                # Extract year from publish date
                year = row['release_year']
                if publish_date:
                    try:
                        year = int(publish_date[:4])
                    except:
                        pass
                
                # Update database
                c.execute('''UPDATE songs 
                    SET length_sec = ?, release_year = ?, vocaloid = ?
                    WHERE id = ?''',
                    (length, year, voicebank if voicebank else row['vocaloid'], row['id']))
                updated += 1
                
                if updated <= 5:
                    print(f'    ✓ {title} -> {length}s, {voicebank}')
            else:
                failed += 1
        else:
            failed += 1
        
        # Rate limiting
        time.sleep(0.3)
    
    conn.commit()
    conn.close()
    
    print(f'\nDone! Updated: {updated}, Failed: {failed}')


if __name__ == '__main__':
    limit = None
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])
    
    enrich_database(limit)
