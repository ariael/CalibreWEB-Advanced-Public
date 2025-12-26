#!/usr/bin/env python
"""
Check Open Library search results - find best match
"""
import requests

authors = ['Isaac Asimov', 'J.K. Rowling']

for author in authors:
    print(f"\n{'='*60}")
    print(f"Search results for: {author}")
    print('='*60)
    
    url = 'https://openlibrary.org/search/authors.json'
    params = {'q': author}
    
    resp = requests.get(url, params=params, timeout=15)
    data = resp.json()
    
    print(f"Total found: {data.get('numFound', 0)}")
    print()
    
    for i, doc in enumerate(data.get('docs', [])[:10]):
        name = doc.get('name', 'N/A')
        key = doc.get('key', 'N/A')
        works = doc.get('work_count', 0)
        birth = doc.get('birth_date', 'N/A')
        
        # Highlight best match (most works)
        marker = ' <-- BEST' if i == 0 and works > 100 else ''
        if works > 100:
            marker = ' <-- BEST (most works)'
        
        print(f"  {i+1}. {name}")
        print(f"     Key: {key}, Works: {works}, Birth: {birth}{marker}")
