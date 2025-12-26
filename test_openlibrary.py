#!/usr/bin/env python
# Test Open Library API
import requests

author = 'Stephen King'
print(f'Testing Open Library API for: {author}')

# Search for author
url = f'https://openlibrary.org/search/authors.json?q={author}'
resp = requests.get(url, timeout=10)
data = resp.json()

if data.get('docs'):
    author_data = data['docs'][0]
    print(f"Found: {author_data.get('name')}")
    print(f"Key: {author_data.get('key')}")
    print(f"Works: {author_data.get('work_count')} books")
    print(f"Birth: {author_data.get('birth_date')}")
    
    # Get full author details
    author_key = author_data.get('key')
    detail_url = f'https://openlibrary.org/authors/{author_key}.json'
    detail_resp = requests.get(detail_url, timeout=10)
    details = detail_resp.json()
    
    bio = details.get('bio')
    if bio:
        if isinstance(bio, dict):
            bio = bio.get('value', '')
        print(f"Bio: {str(bio)[:300]}...")
    else:
        print("Bio: None")
    
    # Get photo
    photo_ids = details.get('photos', [])
    if photo_ids:
        photo_url = f'https://covers.openlibrary.org/a/id/{photo_ids[0]}-L.jpg'
        print(f"Photo: {photo_url}")
    else:
        print("Photo: None")
else:
    print('Not found')
