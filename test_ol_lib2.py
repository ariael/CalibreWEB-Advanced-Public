#!/usr/bin/env python
"""
Test the openlibrary library with correct API
"""
import openlibrary

print("Testing openlibrary library...")
print()

# Correct usage according to docs
api = openlibrary.BookSearch()

# Search by author
print("Searching for Stephen King books...")
res = api.get_by_author('Stephen King')
print(f"Results type: {type(res)}")
print(f"Number of docs: {len(res.docs) if hasattr(res, 'docs') else 'N/A'}")

if hasattr(res, 'docs') and res.docs:
    print("\nFirst 5 books:")
    for doc in res.docs[:5]:
        print(f"  - {doc}")
        if hasattr(doc, 'title'):
            print(f"    Title: {doc.title}")
        if hasattr(doc, 'author_name'):
            print(f"    Author: {doc.author_name}")
