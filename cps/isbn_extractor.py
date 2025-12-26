# -*- coding: utf-8 -*-
import re
import os

def extract_isbn_from_file(file_path):
    """
    Tries to extract ISBN from a binary book file by scanning first and last chunks.
    Works for MOBI, AZW, AZW3, EPUB, PDF (to some extent).
    """
    if not os.path.exists(file_path):
        return None

    # Regex patterns
    # ISBN-13: 978... or 979...
    isbn13_pattern = re.compile(rb'97[89][0-9]{10}')
    # ISBN-10: 10 digits or 9 digits + X
    isbn10_pattern = re.compile(rb'[0-9]{9}[0-9X]')
    
    # Text-based search patterns (looking for ISBN labels)
    # We decode with 'latin-1' or 'utf-8' and ignore errors to see text in binary
    label_patterns = [
        re.compile(r'ISBN(?:-13)?:?\s*(97[89][0-9- ]{10,17})', re.IGNORECASE),
        re.compile(r'ISBN(?:-10)?:?\s*([0-9- ]{9,13}[0-9X])', re.IGNORECASE)
    ]

    def find_in_chunk(chunk):
        # 1. Try label-based search (more accurate)
        text = chunk.decode('latin-1', errors='ignore')
        for pattern in label_patterns:
            matches = pattern.findall(text)
            for match in matches:
                clean = re.sub(r'[^0-9X]', '', match.upper())
                if len(clean) == 13 and clean.startswith(('978', '979')):
                    return clean
                if len(clean) == 10:
                    return clean
        
        # 2. Try raw regex search
        # ISBN-13
        m13 = isbn13_pattern.findall(chunk)
        for m in m13:
            return m.decode('ascii')
            
        # ISBN-10 (more prone to false positives, maybe skip or further validate)
        # m10 = isbn10_pattern.findall(chunk)
        # for m in m10: ...
        
        return None

    try:
        with open(file_path, 'rb') as f:
            # Check beginning (first 64KB)
            start_chunk = f.read(65536)
            res = find_in_chunk(start_chunk)
            if res: return res
            
            # Check end (last 32KB)
            if os.path.getsize(file_path) > 65536:
                f.seek(-32768, os.SEEK_END)
                end_chunk = f.read(32768)
                res = find_in_chunk(end_chunk)
                if res: return res
    except Exception:
        pass

    return None
