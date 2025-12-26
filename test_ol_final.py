#!/usr/bin/env python
"""
Test the new Open Library author enrichment implementation
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
    print(f"\n{'='*60}")
    print(f"Fetching: {author_name}")
    print('='*60)
    
    # Search
    search_url = f'{OPENLIBRARY_BASE}/search/authors.json'
    params = {'q': author_name}
    resp = requests.get(search_url, params=params, timeout=API_TIMEOUT)
    search_data = resp.json()
    
    if not search_data.get('docs'):
        print("  NOT FOUND")
        return None
    
    # Find best match
    author_doc = find_best_author_match(search_data['docs'], author_name)
    author_key = author_doc.get('key')
    print(f"  Found: {author_doc.get('name')} (key: {author_key}, works: {author_doc.get('work_count')})")
    
    # Get details
    detail_url = f'{OPENLIBRARY_BASE}/authors/{author_key}.json'
    detail_resp = requests.get(detail_url, timeout=API_TIMEOUT)
    details = detail_resp.json()
    
    # Bio
    bio = details.get('bio')
    if bio:
        if isinstance(bio, dict):
            bio = bio.get('value', '')
        print(f"  Bio: {str(bio)[:100]}...")
    else:
        print("  Bio: None")
    
    # Photo
    photo_ids = details.get('photos', [])
    valid_photos = [p for p in photo_ids if isinstance(p, int) and p > 0]
    if valid_photos:
        photo_url = f'https://covers.openlibrary.org/a/id/{valid_photos[0]}-L.jpg'
        print(f"  Photo: {photo_url}")
    else:
        print("  Photo: None")
    
    # Works sample
    works_url = f'{OPENLIBRARY_BASE}/authors/{author_key}/works.json?limit=5'
    works_resp = requests.get(works_url, timeout=API_TIMEOUT)
    works_data = works_resp.json()
    
    print(f"  Sample works:")
    for entry in works_data.get('entries', [])[:5]:
        print(f"    - {entry.get('title')}")
    
    if bio or valid_photos:
        print("  ✓ SUCCESS")
        return True
    else:
        print("  ✗ NO DATA")
        return False


# Test authors
authors = [
    "Stephen King",
    "J.K. Rowling",
    "Isaac Asimov",
    "Brandon Sanderson",
    "Terry Pratchett",
    "George R.R. Martin",
    "Neil Gaiman",
]

print("="*60)
print("Open Library Author Enrichment Test")
print("="*60)

success = 0
for author in authors:
    if fetch_author_info(author):
        success += 1

print(f"\n{'='*60}")
print(f"Results: {success}/{len(authors)} authors with data")
print("="*60)
