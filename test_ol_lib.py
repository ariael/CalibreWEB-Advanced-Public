#!/usr/bin/env python
"""
Test the openlibrary library
"""
import openlibrary

print("OpenLibrary library version:", openlibrary.__version__)
print()

# Test search
print("Testing BookSearch...")
results = openlibrary.BookSearch("Stephen King")
print(f"Results type: {type(results)}")
print(f"Results: {results}")

# Try Search class
print("\nTesting Search...")
search = openlibrary.Search("author", "Stephen King")
print(f"Search type: {type(search)}")
print(f"Search: {search}")

# Check Document
print("\nTesting Document...")
try:
    doc = openlibrary.Document("/authors/OL19981A")
    print(f"Document: {doc}")
except Exception as e:
    print(f"Error: {e}")
