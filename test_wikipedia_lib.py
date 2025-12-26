#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test the new wikipedia-based author enrichment
"""
import wikipedia
import hashlib

wikipedia.set_lang("en")

def find_author_photo(images):
    """Find the best candidate for author photo"""
    if not images:
        return None
    
    good_patterns = ['.jpg', '.jpeg', '.png']
    bad_patterns = ['logo', 'icon', 'flag', 'coat_of_arms', 'signature', 'map', 
                    'commons-logo', 'wiki', 'symbol', 'medal', 'award', 'cover',
                    'edit-', 'ambox', 'disambig', 'question_mark']
    
    for img_url in images:
        img_lower = img_url.lower()
        if not any(ext in img_lower for ext in good_patterns):
            continue
        if any(bad in img_lower for bad in bad_patterns):
            continue
        return img_url
    
    for img_url in images:
        if any(ext in img_url.lower() for ext in good_patterns):
            return img_url
    
    return None


def fetch_author_info(author_name):
    """Fetch author info from Wikipedia"""
    try:
        print(f"\n{'='*60}")
        print(f"Fetching: {author_name}")
        print('='*60)
        
        clean_name = author_name.replace('|', ' ').strip()
        search_results = wikipedia.search(clean_name, results=5)
        
        if not search_results:
            print(f"  ✗ No search results")
            return None
        
        print(f"  Search results: {search_results[:3]}")
        
        page = None
        for result in search_results:
            try:
                page = wikipedia.page(result, auto_suggest=False)
                content_lower = page.content[:2000].lower() if page.content else ""
                if any(word in content_lower for word in ['author', 'writer', 'novelist', 'born', 'books', 'wrote']):
                    break
            except wikipedia.DisambiguationError as e:
                print(f"  Disambiguation: {e.options[:3]}")
                for option in e.options[:10]:
                    if 'author' in option.lower() or 'writer' in option.lower():
                        try:
                            page = wikipedia.page(option, auto_suggest=False)
                            break
                        except:
                            continue
                if page:
                    break
            except wikipedia.PageError:
                continue
            except Exception as e:
                print(f"  Error: {e}")
                continue
        
        if not page:
            print(f"  ✗ Could not find valid page")
            return None
        
        print(f"  Found page: {page.title}")
        print(f"  URL: {page.url}")
        
        biography = page.summary[:500] if page.summary else None
        if biography:
            print(f"  Bio: {biography[:150]}...")
        
        image_url = find_author_photo(page.images)
        if image_url:
            print(f"  Photo: {image_url[:70]}...")
        else:
            print(f"  Photo: None found")
        
        if biography or image_url:
            print(f"  ✓ SUCCESS")
            return {"biography": biography, "image_url": image_url}
        else:
            print(f"  ✗ No useful data")
            return None

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


if __name__ == "__main__":
    # Test authors
    test_authors = [
        "Stephen King",
        "J.K. Rowling",
        "Brandon Sanderson",
        "Isaac Asimov",
        "Terry Pratchett",
        "George R.R. Martin",
        "Neil Gaiman",
    ]
    
    print("="*60)
    print("Wikipedia Author Enrichment Test")
    print("="*60)
    
    success = 0
    for author in test_authors:
        result = fetch_author_info(author)
        if result:
            success += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {success}/{len(test_authors)} authors found")
    print("="*60)
