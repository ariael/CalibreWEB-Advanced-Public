#!/usr/bin/env python
"""
Explore openlibrary library structure
"""
import openlibrary

print("Testing openlibrary library...")

api = openlibrary.BookSearch()

# Search by author
print("\nSearching for 'Stephen King'...")
res = api.get_by_author('Stephen King')
print(f"Results: {len(res.docs)} documents")

# Explore first document
if res.docs:
    doc = res.docs[0]
    print(f"\nFirst document type: {type(doc)}")
    print(f"Document attributes: {dir(doc)}")
    
    # Try to get attributes
    for attr in ['title', 'author_name', 'author_key', 'cover_i', 'key', 'first_publish_year']:
        if hasattr(doc, attr):
            val = getattr(doc, attr, None)
            print(f"  {attr}: {val}")

# Try Search class for authors
print("\n\nTrying Search class for authors...")
author_search = openlibrary.Search("authors", "Stephen King")
print(f"Search type: {type(author_search)}")
print(f"Search dir: {dir(author_search)}")

# Try to get results
if hasattr(author_search, 'get'):
    results = author_search.get()
    print(f"Results: {results}")
