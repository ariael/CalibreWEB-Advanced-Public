#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test author enrichment directly
"""
import requests
import hashlib

USER_AGENT = 'CalibreWeb/1.0 (https://github.com/janeczku/calibre-web; author-enrichment)'
API_HEADERS = {'User-Agent': USER_AGENT}

def fetch_author_info(author_name):
    """
    Fetches author biography and image URL from Wikidata/Wikipedia.
    """
    try:
        print(f"Fetching info for: {author_name}")
        
        # 1. Search Wikidata
        search_url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "search": author_name,
            "type": "item"
        }
        resp = requests.get(search_url, params=params, headers=API_HEADERS, timeout=10)
        data = resp.json()

        if not data.get("search"):
            print(f"  No Wikidata entry found")
            return None

        entity_id = data["search"][0]["id"]
        print(f"  Found Wikidata entity: {entity_id}")
        
        # 2. Get entity details
        entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
        resp = requests.get(entity_url, headers=API_HEADERS, timeout=10)
        entity_data = resp.json()["entities"][entity_id]

        # 3. Get Image URL (P18)
        image_url = None
        claims = entity_data.get("claims", {})
        if "P18" in claims:
            image_file = claims["P18"][0]["mainsnak"]["datavalue"]["value"]
            name_space = image_file.replace(" ", "_")
            md5 = hashlib.md5(name_space.encode('utf-8')).hexdigest()
            image_url = f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{name_space}"
            print(f"  Image URL: {image_url[:70]}...")

        # 4. Get Biography
        biography = None
        sitelinks = entity_data.get("sitelinks", {})
        if "enwiki" in sitelinks:
            wiki_title = sitelinks["enwiki"]["title"]
            wiki_api_url = "https://en.wikipedia.org/w/api.php"
            wiki_params = {
                "action": "query",
                "format": "json",
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "titles": wiki_title
            }
            wiki_resp = requests.get(wiki_api_url, params=wiki_params, headers=API_HEADERS, timeout=10)
            wiki_data = wiki_resp.json()
            pages = wiki_data.get("query", {}).get("pages", {})
            for page_id in pages:
                if "extract" in pages[page_id]:
                    biography = pages[page_id]["extract"]
                    print(f"  Biography: {biography[:100]}...")
                    break
        
        if not biography:
            biography = entity_data.get("descriptions", {}).get("en", {}).get("value")
            if biography:
                print(f"  Fallback bio: {biography}")

        return {
            "biography": biography,
            "image_url": image_url,
            "name": author_name
        }

    except Exception as e:
        print(f"  Error: {e}")
        return None


if __name__ == "__main__":
    # Test with some common authors - you can change these to authors in your library
    test_authors = [
        "Stephen King",
        "J.K. Rowling", 
        "Brandon Sanderson",
        "Isaac Asimov",
        "Terry Pratchett",
    ]
    
    print("=" * 60)
    print("Author Enrichment Test")
    print("=" * 60)
    
    success = 0
    for author in test_authors:
        result = fetch_author_info(author)
        if result and (result.get("biography") or result.get("image_url")):
            success += 1
            print(f"  ✓ SUCCESS\n")
        else:
            print(f"  ✗ FAILED\n")
    
    print("=" * 60)
    print(f"Results: {success}/{len(test_authors)} authors found")
    print("=" * 60)
