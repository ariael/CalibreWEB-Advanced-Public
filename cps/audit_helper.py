# -*- coding: utf-8 -*-
import os
import zipfile
from lxml import etree
import docx
from . import logger

log = logger.create()

CZECH_CHARS = set("áéíóúůýčďěňřšťžÁÉÍÓÚŮÝČĎĚŇŘŠŤŽ")

def extract_text_from_epub(file_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # Look for the first xhtml/html file that is likely content
            content_files = [f for f in z.namelist() if f.endswith(('.xhtml', '.html', '.htm'))]
            if not content_files:
                return ""
            
            # Read a sample from the first few content files
            text_sample = ""
            for cf in content_files[:3]:
                with z.open(cf) as f:
                    tree = etree.parse(f, etree.HTMLParser())
                    # Extract text content
                    text = "".join(tree.xpath("//text()"))
                    text_sample += text
                    if len(text_sample) > 10000:
                        break
            return text_sample
    except Exception as e:
        log.error("Failed to extract text from EPUB %s: %s", file_path, e)
        return ""

def extract_text_from_docx(file_path):
    try:
        # Add file size check to avoid processing huge files
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size > 50 * 1024 * 1024:  # Skip files larger than 50MB
                log.warning("Skipping large DOCX file %s (%d MB)", file_path, file_size / (1024*1024))
                return ""
        
        doc = docx.Document(file_path)
        text_sample = ""
        para_count = 0
        for para in doc.paragraphs:
            if para_count >= 50:  # Limit to first 50 paragraphs
                break
            text_sample += para.text + " "
            para_count += 1
            if len(text_sample) > 10000:
                break
        return text_sample
    except FileNotFoundError:
        log.error("DOCX file not found: %s", file_path)
        return ""
    except Exception as e:
        log.error("Failed to extract text from DOCX %s: %s", file_path, str(e))
        return ""

def is_czech_content(file_path, extension):
    if not os.path.exists(file_path):
        return False
        
    text = ""
    ext = extension.lower().strip('.')
    if ext == 'epub':
        text = extract_text_from_epub(file_path)
    elif ext == 'docx':
        text = extract_text_from_docx(file_path)
    else:
        # For AZW/AZW3 or other formats we don't scan yet,
        # we assume they are NOT the translated Czech version (i.e. return False)
        # so they count towards the "Original" (has_azw) slot.
        return False

    if not text:
        return False
        
    # Heuristic: Count Czech diacritics
    cz_char_count = sum(1 for char in text if char in CZECH_CHARS)
    
    # If more than 0.5% of characters are Czech diacritics, it's very likely Czech
    # (Typical Czech text has ~2-5% diacritics)
    if len(text) > 0 and (cz_char_count / len(text)) > 0.005:
        return True
        
    # Fallback: specific common words if char count is low (e.g. short text)
    common_cz = [" se ", " je ", " že ", " s ", " v ", " na ", " pro "]
    lower_text = text.lower()
    matches = sum(1 for word in common_cz if word in lower_text)
    if matches >= 2:
        return True
        
    return False

def detect_text_language(text):
    if not text or not text.strip():
        return "unknown"
        
    lower_text = text.lower()
    
    # Check for Czech diacritics
    cz_char_count = sum(1 for char in text if char in CZECH_CHARS)
    if len(text) > 0 and (cz_char_count / len(text)) > 0.01:
        return "ces" # ISO 639-2 Czech
        
    # Check for common Czech particles
    common_cz = [" se ", " je ", " že ", " s ", " v ", " na ", " pro "]
    cz_matches = sum(1 for word in common_cz if word in lower_text)
    
    # Check for common English words
    common_en = [" the ", " and ", " is ", " in ", " with ", " for ", " of ", " that ", " this "]
    en_matches = sum(1 for word in common_en if word in lower_text)
    
    if cz_matches > en_matches and cz_matches >= 1:
        return "ces"
    if en_matches >= 2:
        return "eng"
        
    return "unknown"

def get_book_health(book, library_path, quick=False):
    formats = [d.format.upper() for d in book.data]
    
    has_azw = False
    has_epub = False
    has_docx_cz = False
    extra_formats = []

    for d in book.data:
        fmt = d.format.upper()
        # Construct absolute path to the file
        file_path = os.path.join(library_path, book.path, d.name + "." + d.format.lower())

        if fmt in ['AZW', 'AZW3']:
            # AZW/AZW3 must NOT be Czech (should be Original/English)
            # In quick mode, we assume they are NOT Czech without scanning
            if not quick and is_czech_content(file_path, fmt):
                # Is Czech -> Invalid for AZW slot
                pass 
            else:
                has_azw = True
        
        elif fmt == 'EPUB':
            # EPUB just needs to exist
            has_epub = True
            
        elif fmt == 'DOCX':
            # DOCX must be Czech
            # In quick mode, we assume it's Czech if the book language is Czech or if it's the only DOCX
            is_cz = False
            if quick:
                # Check DB languages
                book_langs = [l.lang_code for l in book.languages]
                if "ces" in book_langs or not book_langs:
                    is_cz = True
            else:
                if is_czech_content(file_path, fmt):
                    is_cz = True
            
            if is_cz:
                has_docx_cz = True
            else:
                # If it's not Czech, it's considered an "extra" unwanted format
                extra_formats.append(f"DOCX (non-CZ)")
        
        else:
            # Any other format is extra
            extra_formats.append(fmt)

    desc_text = book.comments[0].text if book.comments else ""
    desc_lang = detect_text_language(desc_text)
    
    is_healthy = has_azw and has_docx_cz and has_epub and not extra_formats and desc_lang in ["ces", "eng"]
    return {
        'is_healthy': is_healthy,
        'desc_lang': desc_lang,
        'extra_formats': extra_formats,
        'has_azw': has_azw,
        'has_epub': has_epub,
        'has_docx_cz': has_docx_cz
    }
