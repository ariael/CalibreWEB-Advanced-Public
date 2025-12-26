#!/usr/bin/env python
"""
Direct test of Open Library API - without Calibre-Web imports
"""
import requests
import hashlib

API_TIMEOUT = 15
OPENLIBRARY_BASE = 'https://openlibrary.org'

def find_best_author_match(docs, author_name):
    """Find best matching author (most works)"""
    if not docs:
        return None
    sorted_docs = sorted(docs, key=lambda x: x.get('work_count', 0), reverse=True)
    if sorted_docs[0].get('work_count', 0) > 10:
        return sorted_docs[0]
    author_lower = author_name.lower().strip()
    for doc in docs:
        if doc.get('name', '').lower().strip() == author_lower:
            return doc
    return docs[0] if docs else None


def fetch_author_info(author_name):
    """Fetch author from Open Library"""
    try:
        search_url = f'{OPENLIBRARY_BASE}/search/authors.json'
        params = {'q': author_name}
        resp = requests.get(search_url, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        search_data = resp.json()
        
        if not search_data.get('docs'):
            return None
        
        author_doc = find_best_author_match(search_data['docs'], author_name)
        if not author_doc:
            return None
        
        author_key = author_doc.get('key')
        work_count = author_doc.get('work_count', 0)
        
        # Get details
        detail_url = f'{OPENLIBRARY_BASE}/authors/{author_key}.json'
        detail_resp = requests.get(detail_url, timeout=API_TIMEOUT)
        detail_resp.raise_for_status()
        details = detail_resp.json()
        
        bio = details.get('bio')
        if bio:
            if isinstance(bio, dict):
                bio = bio.get('value', '')
            bio = str(bio)[:2000] if bio else None
        
        photo_url = None
        photo_ids = details.get('photos', [])
        if photo_ids:
            valid_photos = [p for p in photo_ids if isinstance(p, int) and p > 0]
            if valid_photos:
                photo_url = f'https://covers.openlibrary.org/a/id/{valid_photos[0]}-L.jpg'
        
        return {
            "biography": bio,
            "image_url": photo_url,
            "work_count": work_count,
            "author_key": author_key
        }
    except Exception as e:
        print(f"Error: {e}")
        return None


print("="*60)
print("Testing Open Library API directly")
print("="*60)

test_authors = [
    "Stephen King",
    "Atamanov, Michael",
    "Michael Atamanov",
    "Michael Atamanov author",
]

for author in test_authors:
    result = fetch_author_info(author)
    print(f"\n{author}:")
    if result:
        print(f"  Key: {result.get('author_key')}")
        print(f"  Works: {result.get('work_count', 0)}")
        print(f"  Bio: {str(result.get('biography', ''))[:100]}...")
        print(f"  Image: {result.get('image_url')}")
        print(f"  ✓ SUCCESS")
    else:
        print(f"  ✗ NOT FOUND")
