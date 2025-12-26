#!/usr/bin/env python
"""
Compare Wikipedia vs Open Library for author data
"""
import requests
import wikipedia

wikipedia.set_lang("en")

AUTHORS = [
    "Stephen King",
    "J.K. Rowling", 
    "Brandon Sanderson",
    "Isaac Asimov",
    "Terry Pratchett",
    "George R.R. Martin",
    "Neil Gaiman",
]


def test_openlibrary(author_name):
    """Test Open Library API"""
    try:
        url = f'https://openlibrary.org/search/authors.json?q={author_name}'
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if not data.get('docs'):
            return None
        
        author_data = data['docs'][0]
        author_key = author_data.get('key')
        
        # Get full details
        detail_url = f'https://openlibrary.org/authors/{author_key}.json'
        detail_resp = requests.get(detail_url, timeout=10)
        details = detail_resp.json()
        
        bio = details.get('bio')
        if bio and isinstance(bio, dict):
            bio = bio.get('value', '')
        
        photo_ids = details.get('photos', [])
        photo_url = f'https://covers.openlibrary.org/a/id/{photo_ids[0]}-L.jpg' if photo_ids else None
        
        return {
            'bio': bool(bio),
            'photo': bool(photo_url),
            'photo_url': photo_url
        }
    except Exception as e:
        return {'error': str(e)}


def test_wikipedia(author_name):
    """Test Wikipedia library"""
    try:
        search_results = wikipedia.search(author_name, results=3)
        if not search_results:
            return None
        
        page = wikipedia.page(search_results[0], auto_suggest=False)
        
        bio = page.summary[:500] if page.summary else None
        
        # Find photo (filter out logos)
        photo_url = None
        for img in page.images:
            img_lower = img.lower()
            if any(ext in img_lower for ext in ['.jpg', '.jpeg', '.png']):
                if not any(bad in img_lower for bad in ['logo', 'icon', 'flag', 'wiki', 'symbol']):
                    photo_url = img
                    break
        
        return {
            'bio': bool(bio),
            'photo': bool(photo_url),
            'photo_url': photo_url
        }
    except Exception as e:
        return {'error': str(e)}


print("="*80)
print("Comparing Wikipedia vs Open Library for Author Data")
print("="*80)
print(f"{'Author':<25} | {'Wikipedia':<20} | {'Open Library':<20}")
print("-"*80)

wiki_score = 0
ol_score = 0

for author in AUTHORS:
    wiki = test_wikipedia(author)
    ol = test_openlibrary(author)
    
    wiki_status = "✓ bio+photo" if wiki and wiki.get('bio') and wiki.get('photo') else \
                  "✓ bio only" if wiki and wiki.get('bio') else \
                  "✗ nothing" if wiki else "✗ error"
    
    ol_status = "✓ bio+photo" if ol and ol.get('bio') and ol.get('photo') else \
                "✓ bio only" if ol and ol.get('bio') else \
                "✗ nothing" if ol else "✗ error"
    
    if wiki and wiki.get('bio') and wiki.get('photo'):
        wiki_score += 2
    elif wiki and wiki.get('bio'):
        wiki_score += 1
        
    if ol and ol.get('bio') and ol.get('photo'):
        ol_score += 2
    elif ol and ol.get('bio'):
        ol_score += 1
    
    print(f"{author:<25} | {wiki_status:<20} | {ol_status:<20}")

print("-"*80)
print(f"{'SCORE':<25} | {wiki_score:<20} | {ol_score:<20}")
print("="*80)

if ol_score > wiki_score:
    print("\n>>> Open Library is BETTER for author data!")
elif wiki_score > ol_score:
    print("\n>>> Wikipedia is BETTER for author data!")
else:
    print("\n>>> Both are EQUAL")
