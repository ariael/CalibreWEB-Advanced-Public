#!/usr/bin/env python
"""
Direct test of author enrichment - simulates what Calibre-Web does
"""
import sys
import os

# Add repo to path
sys.path.insert(0, 'c:/GitHub/CalibreWEB/repo')

# Set up minimal environment
os.environ.setdefault('CALIBRE_WEB_CONFIG', 'c:/GitHub/CalibreWEB/repo')

# Test the fetch function directly (without DB)
from cps.services.author_enrichment import fetch_author_info

print("="*60)
print("Testing fetch_author_info directly")
print("="*60)

test_authors = [
    "Stephen King",
    "Atamanov, Michael",
    "Michael Atamanov",
]

for author in test_authors:
    result = fetch_author_info(author)
    print(f"\n{author}:")
    if result:
        print(f"  Bio: {str(result.get('biography', ''))[:80]}...")
        print(f"  Image: {result.get('image_url')}")
        print(f"  Works: {result.get('work_count', 0)}")
        print(f"  ✓ SUCCESS")
    else:
        print(f"  ✗ NOT FOUND")
