#!/usr/bin/env python
"""
Test Open Library API properly
"""
import requests

authors = ['Isaac Asimov', 'J.K. Rowling', 'Stephen King', 'Brandon Sanderson', 'Terry Pratchett']

for author in authors:
    print(f"\n{'='*60}")
    print(f"Testing: {author}")
    print('='*60)
    
    # Search for author
    url = 'https://openlibrary.org/search/authors.json'
    params = {'q': author}
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"Status: {resp.status_code}")
        
        data = resp.json()
        num_found = data.get('numFound', 0)
        print(f"Results found: {num_found}")
        
        if data.get('docs'):
            doc = data['docs'][0]
            name = doc.get('name')
            key = doc.get('key')
            work_count = doc.get('work_count')
            birth = doc.get('birth_date')
            
            print(f"  Name: {name}")
            print(f"  Key: {key}")
            print(f"  Works: {work_count}")
            print(f"  Birth: {birth}")
            
            # Get author details
            if key:
                detail_url = f'https://openlibrary.org/authors/{key}.json'
                detail_resp = requests.get(detail_url, timeout=15)
                details = detail_resp.json()
                
                bio = details.get('bio')
                if bio:
                    if isinstance(bio, dict):
                        bio = bio.get('value', '')
                    print(f"  Bio: {str(bio)[:150]}...")
                else:
                    print("  Bio: None")
                
                photos = details.get('photos', [])
                if photos:
                    photo_url = f'https://covers.openlibrary.org/a/id/{photos[0]}-L.jpg'
                    print(f"  Photo: {photo_url}")
                else:
                    print("  Photo: None")
                
                # Get works/books
                works_url = f'https://openlibrary.org/authors/{key}/works.json?limit=5'
                works_resp = requests.get(works_url, timeout=15)
                works_data = works_resp.json()
                
                entries = works_data.get('entries', [])
                print(f"  Sample books ({len(entries)} shown):")
                for work in entries[:5]:
                    title = work.get('title', 'Unknown')
                    print(f"    - {title}")
        else:
            print("  NOT FOUND!")
            
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*60)
print("Test complete!")
