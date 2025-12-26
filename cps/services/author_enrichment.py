# -*- coding: utf-8 -*-
"""
Author Enrichment Service with Multi-Source Provider Architecture.

Inspired by Calibre Desktop plugins, this service aggregates metadata from:
- Databazeknih.cz (Premium source for CZ/SK authors, bios, and series)
- Open Library (Global bibliography and portraits)
- Wikipedia (Multi-language biographies)
"""

import requests
import hashlib
import random
import re
from datetime import datetime, timezone, timedelta
from lxml.html import fromstring
from urllib.parse import quote, urlparse
from .. import logger, ub
from .isbn_extractor import extract_isbn_from_file

log = logger.create()

# API Configuration
API_TIMEOUT = 15
OPENLIBRARY_BASE = 'https://openlibrary.org'
DATABAZEKNIH_BASE = 'https://www.databazeknih.cz'

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
]

def get_headers():
    return {'User-Agent': random.choice(USER_AGENTS)}

def calculate_content_hash(biography, image_url):
    """Calculate MD5 hash of content for change detection"""
    content = f"{biography or ''}{image_url or ''}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def clean_author_name(name):
    """Smartly cleans author name for search."""
    if not name:
        return []
    
    clean = name.replace('|', ' ').strip()
    variations = [clean]
    
    if ',' in clean:
        parts = [p.strip() for p in clean.split(',')]
        if len(parts) == 2:
            variations.append(f"{parts[1]} {parts[0]}")
    
    variations.append(clean.replace(',', ''))
    return list(set(variations))

def normalize_book_title(title):
    """Standardizes book title for comparison"""
    if not title:
        return ""
    t = title.lower().strip()
    # Remove common start words
    for word in [r'^the\s+', r'^a\s+', r'^an\s+', r'^ten\s+', r'^ta\s+', r'^to\s+', r'^der\s+', r'^die\s+', r'^das\s+']:
        t = re.sub(word, '', t)
    # Remove non-alphanumeric
    t = re.sub(r'[^a-z0-9]', '', t)
    return t


# --- Providers ---

class AuthorMetadataSource:
    def fetch(self, author_name, isbn=None):
        raise NotImplementedError

class OpenLibrarySource(AuthorMetadataSource):
    def fetch(self, author_name, isbn=None):
        try:
            author_key = None
            if isbn:
                # Try finding author via ISBN first
                isbn_url = f'https://openlibrary.org/isbn/{isbn}.json'
                resp = requests.get(isbn_url, timeout=API_TIMEOUT)
                if resp.status_code == 200:
                    book_data = resp.json()
                    authors = book_data.get('authors', [])
                    if authors:
                        author_key = authors[0].get('key')

            if not author_key:
                # Search by name
                search_url = f'{OPENLIBRARY_BASE}/search/authors.json'
                params = {'q': author_name}
                resp = requests.get(search_url, params=params, timeout=API_TIMEOUT)
                search_data = resp.json()
                if search_data.get('docs'):
                    # Legacy helper find_best_author_match
                    author_doc = find_best_author_match(search_data['docs'], author_name)
                    if author_doc:
                        author_key = author_doc.get('key')

            if author_key:
                if not author_key.startswith('/authors/'):
                    author_key = f'/authors/{author_key}'
                
                detail_url = f'{OPENLIBRARY_BASE}{author_key}.json'
                resp = requests.get(detail_url, timeout=API_TIMEOUT)
                data = resp.json()
                
                bio = data.get('bio', '')
                if isinstance(bio, dict): bio = bio.get('value', '')
                
                photo_url = None
                photos = data.get('photos', [])
                if photos and isinstance(photos[0], int) and photos[0] > 0:
                    photo_url = f'https://covers.openlibrary.org/a/id/{photos[0]}-L.jpg'
                
                # Bibliography
                works = []
                try:
                    works_url = f'{OPENLIBRARY_BASE}{author_key}/works.json?limit=100'
                    works_resp = requests.get(works_url, timeout=API_TIMEOUT)
                    works_data = works_resp.json()
                    works = [e.get('title') for e in works_data.get('entries', []) if e.get('title')]
                except: pass

                return {
                    'biography': bio or '',
                    'image_url': photo_url,
                    'name': data.get('name'),
                    'works': list(set(works)),
                    'source': 'openlibrary'
                }
        except Exception as e:
            log.debug("Open Library source failed: %s", e)
        return None

class WikipediaSource(AuthorMetadataSource):
    def fetch(self, author_name, isbn=None):
        # Wraps the previous wikipedia logic
        try:
            headers = get_headers()
            search_url = "https://en.wikipedia.org/w/api.php"
            name_variations = clean_author_name(author_name)
            
            for clean_name in name_variations:
                params = {'action': 'query', 'list': 'search', 'srsearch': clean_name, 'format': 'json', 'srlimit': 3}
                resp = requests.get(search_url, params=params, headers=headers, timeout=10)
                results = resp.json().get("query", {}).get("search", [])
                if not results: continue
                
                title = results[0]["title"]
                info_params = {
                    "action": "query", "prop": "extracts|pageimages", "exintro": True, "exsentences": 12,
                    "explaintext": True, "redirects": 1, "titles": title, "format": "json", "pithumbsize": 1000
                }
                info_resp = requests.get(search_url, params=info_params, headers=headers, timeout=10)
                pages = info_resp.json().get("query", {}).get("pages", {})
                
                for pid, pdata in pages.items():
                    if pid == "-1": continue
                    extract = pdata.get("extract", "")
                    if not extract: continue
                    # Rough filter for authors
                    if any(w in extract.lower() for w in ['author', 'writer', 'born', 'books', 'novelist', 'poet']):
                        return {
                            "biography": extract,
                            "image_url": pdata.get("thumbnail", {}).get("source"),
                            "name": title,
                            "source": "wikipedia"
                        }
        except Exception as e:
            log.debug("Wikipedia source failed: %s", e)
        return None

class DatabazeknihSource(AuthorMetadataSource):
    def fetch(self, author_name, isbn=None):
        try:
            headers = get_headers()
            q = quote(author_name)
            search_url = f"{DATABAZEKNIH_BASE}/vyhledavani/autori?q={q}"
            resp = requests.get(search_url, headers=headers, timeout=API_TIMEOUT)
            root = fromstring(resp.content)
            
            # Find candidate links
            results = root.xpath("//a[contains(@href, 'autori/') and not(contains(@href, 'vyhledavani'))]")
            if not results: return None
            
            href = results[0].get("href")
            slug = href.split("/")[-1]
            profile_url = DATABAZEKNIH_BASE + "/" + href.lstrip("/")
            
            # 1. Main Profile (Image)
            prof_resp = requests.get(profile_url, headers=headers, timeout=API_TIMEOUT)
            prof_root = fromstring(prof_resp.content)
            
            photo_url = ""
            img_div = prof_root.xpath("//div[contains(@class, 'img_author_detail')]")
            if img_div:
                style = img_div[0].get("style", "")
                match = re.search(r'url\("(.*?)"\)', style)
                if match:
                    photo_url = match.group(1)
                    if not photo_url.startswith("http"):
                        photo_url = DATABAZEKNIH_BASE + "/" + photo_url.lstrip("/")
            
            # 2. Biography
            bio = ""
            bio_url = f"{DATABAZEKNIH_BASE}/zivotopis/{slug}"
            bio_resp = requests.get(bio_url, headers=headers, timeout=API_TIMEOUT)
            bio_root = fromstring(bio_resp.content)
            
            bio_header = bio_root.xpath("//h2[contains(@class, 'lora') and contains(text(), 'ivotopis')]")
            if bio_header:
                curr = bio_header[0].getnext()
                while curr is not None and curr.tag == 'p' and curr.get('class') == 'new2':
                    bio += curr.text_content().strip() + "\n\n"
                    curr = curr.getnext()
            
            if not bio: # Fallback to short bio
                bio_nodes = prof_root.xpath("//p[@class='justify small']")
                bio = "\n\n".join([n.text_content().strip() for n in bio_nodes])
            
            # 3. Bibliography
            works = []
            works_url = f"{DATABAZEKNIH_BASE}/vydane-knihy/{slug}"
            try:
                w_resp = requests.get(works_url, headers=headers, timeout=API_TIMEOUT)
                w_root = fromstring(w_resp.content)
                w_nodes = w_root.xpath("//div[contains(@class, 'book-triangle-container')]//a[contains(@class, 'new')]")
                works = [n.text_content().strip() for n in w_nodes if n.text_content().strip()]
            except: pass
            
            if not works:
                 w_nodes = prof_root.xpath("//table[contains(@class, 'new2')]//a[contains(@class, 'new')]")
                 works = [n.text_content().strip() for n in w_nodes if n.text_content().strip()]

            return {
                "biography": bio.strip(),
                "image_url": photo_url,
                "name": author_name,
                "works": list(set(works)),
                "source": "databazeknih"
            }
        except Exception as e:
            log.debug("Databazeknih source failed: %s", e)
        return None

class GoodreadsSource(AuthorMetadataSource):
    def fetch(self, author_name, isbn=None):
        try:
            headers = get_headers()
            q = quote(author_name)
            # search_type=people to find author profiles
            search_url = f"https://www.goodreads.com/search?q={q}&search_type=people"
            resp = requests.get(search_url, headers=headers, timeout=API_TIMEOUT)
            root = fromstring(resp.content)
            
            # Find author link
            results = root.xpath("//a[contains(@class, 'authorName') and contains(@href, '/author/show/')]")
            if not results: return None
            
            author_url = "https://www.goodreads.com" + results[0].get("href")
            resp = requests.get(author_url, headers=headers, timeout=API_TIMEOUT)
            root = fromstring(resp.content)
            
            # Bio: usually in .description or similar
            bio = ""
            bio_node = root.xpath("//div[contains(@class, 'description')]//span[last()]")
            if bio_node: bio = bio_node[0].text_content().strip()
            
            # Photo
            photo_url = ""
            img_node = root.xpath("//div[contains(@class, 'leftContainer')]//img/@src")
            if img_node: photo_url = img_node[0]
            
            # Works
            works = []
            works_node = root.xpath("//a[contains(@class, 'bookTitle')]/span/text()")
            works = [w.strip() for w in works_node if w.strip()]

            return {
                "biography": bio,
                "image_url": photo_url,
                "name": author_name,
                "works": list(set(works)),
                "source": "goodreads"
            }
        except Exception as e:
            log.debug("Goodreads source failed: %s", e)
        return None

class AmazonSource(AuthorMetadataSource):
    def fetch(self, author_name, isbn=None):
        try:
            # Amazon is harder due to bot protection, but we try basic search
            headers = get_headers()
            q = quote(author_name)
            search_url = f"https://www.amazon.com/s?k={q}&i=stripbooks"
            resp = requests.get(search_url, headers=headers, timeout=API_TIMEOUT)
            root = fromstring(resp.content)
            
            # Look for author page link
            author_links = root.xpath("//a[contains(@href, '/-/en/e/B') or contains(@href, '/author/')]")
            if not author_links: return None
            
            author_url = "https://www.amazon.com" + author_links[0].get("href") if not author_links[0].get("href").startswith("http") else author_links[0].get("href")
            resp = requests.get(author_url, headers=headers, timeout=API_TIMEOUT)
            root = fromstring(resp.content)
            
            # Bio
            bio = ""
            bio_node = root.xpath("//div[@id='author-bio-text'] or //span[contains(@id, 'AuthorBio')]")
            if bio_node: bio = bio_node[0].text_content().strip()
            
            # Photo
            photo_url = ""
            img_node = root.xpath("//img[@id='author-image']/@src")
            if img_node: photo_url = img_node[0]

            return {
                "biography": bio,
                "image_url": photo_url,
                "name": author_name,
                "source": "amazon"
            }
        except Exception as e:
            log.debug("Amazon source failed: %s", e)
        return None

# --- Legacy Helpers ---

def find_best_author_match(docs, author_name):
    if not docs: return None
    sorted_docs = sorted(docs, key=lambda x: x.get('work_count', 0), reverse=True)
    if sorted_docs[0].get('work_count', 0) > 10: return sorted_docs[0]
    author_lower = author_name.lower().strip()
    for doc in docs:
        if doc.get('name', '').lower().strip() == author_lower: return doc
    return docs[0]

# --- Main Logic ---

def fetch_author_info(author_name, isbn=None):
    """Refactored main entry point with multi-source merging."""
    providers = [
        DatabazeknihSource(),
        GoodreadsSource(),
        OpenLibrarySource(),
        WikipediaSource(),
        AmazonSource()
    ]
    
    final_data = {
        'biography': '',
        'image_url': '',
        'name': author_name,
        'works': [],
        'sources': []
    }
    
    for provider in providers:
        res = provider.fetch(author_name, isbn)
        if res:
            final_data['sources'].append(res['source'])
            # Bio: Prefer longer
            if len(res.get('biography', '')) > len(final_data['biography']):
                final_data['biography'] = res['biography']
            # Photo: Prefer first non-empty, or prioritize sources
            if not final_data['image_url'] and res.get('image_url'):
                final_data['image_url'] = res['image_url']
            # Works: Merge
            if res.get('works'):
                final_data['works'].extend(res['works'])
                final_data['works'] = list(set(final_data['works']))
            # Name: Prefer from specific sources if it differs significantly
            if res['source'] == 'databazeknih' and len(res['name']) > 3:
                final_data['name'] = res['name']
    
    if not final_data['sources']:
        return None
        
    # Calculate hash for sync logic
    final_data['content_hash'] = calculate_content_hash(final_data['biography'], final_data['image_url'])
    log.info("Enriched %s from sources: %s", author_name, ", ".join(final_data['sources']))
    return final_data


def get_author_info(author_id, author_name, force_refresh=False, is_initial_load=False, commit=True):
    """Checks cache and returns enriched author info."""
    now = datetime.now()
    isbn_hint = None
    
    author_info = ub.session.query(ub.AuthorInfo).filter(ub.AuthorInfo.author_id == author_id).first()
    needs_fetch = force_refresh or not author_info or not author_info.last_checked
    if author_info and author_info.last_checked and (now - author_info.last_checked).days >= 30:
        needs_fetch = True
            
    if needs_fetch:
        try:
            from .. import db, config
            calibre_path = config.config_calibre_dir
            author = db.session.query(db.Authors).filter(db.Authors.id == author_id).first()
            if author and author.books:
                # 1. Search DB for ISBN
                for b in author.books:
                    if b.isbn:
                        isbn_hint = b.isbn.strip().replace('-', '')
                        if len(isbn_hint) >= 10: break
                
                # 2. If still no ISBN, try extracting from top 3 book files
                if not isbn_hint:
                    log.info("No ISBN in DB for %s, trying file extraction", author_name)
                    for b in author.books[:3]:
                        if b.data:
                            for d in b.data:
                                # Full path assembly: calibre_dir / book_path / file_name.ext
                                file_path = os.path.join(calibre_path, b.path, d.name + "." + d.format.lower())
                                extracted = extract_isbn_from_file(file_path)
                                if extracted:
                                    isbn_hint = extracted
                                    log.info("Extracted ISBN %s from file: %s", extracted, file_path)
                                    break
                        if isbn_hint: break
        except Exception as e:
            log.debug("ISBN hint discovery failed for %s: %s", author_name, e)

        new_data = fetch_author_info(author_name, isbn=isbn_hint)
        
        if new_data:
            new_hash = new_data["content_hash"]
            if not author_info:
                last_checked_time = now - timedelta(days=random.randint(0, 30)) if is_initial_load else now
                author_info = ub.AuthorInfo(
                    author_id=author_id,
                    author_name=author_name,
                    suggested_name=new_data["name"] if new_data["name"] != author_name else None,
                    biography=new_data["biography"],
                    image_url=new_data["image_url"],
                    works=new_data.get("works", []),
                    content_hash=new_hash,
                    last_updated=now,
                    last_checked=last_checked_time
                )
                ub.session.add(author_info)
            else:
                author_info.last_checked = now
                if author_info.content_hash != new_hash or force_refresh:
                    author_info.biography = new_data["biography"]
                    author_info.image_url = new_data["image_url"]
                    author_info.works = new_data.get("works", [])
                    author_info.content_hash = new_hash
                    author_info.last_updated = now
                    if new_data["name"] != author_info.author_name:
                        author_info.suggested_name = new_data["name"]
            
            if commit:
                try:
                    ub.session.commit()
                except: ub.session.rollback()
        elif author_info:
            author_info.last_checked = now
            if commit:
                try: ub.session.commit()
                except: ub.session.rollback()

    return author_info

def get_missing_books(author_id):
    """Compares cached bibliography with library."""
    try:
         from .. import db
         info = ub.session.query(ub.AuthorInfo).filter(ub.AuthorInfo.author_id == author_id).first()
         if not info or not info.works: return []
         
         books = calibre_db.session.query(db.Books).join(db.books_authors_link).filter(db.books_authors_link.c.author == author_id).all()
         owned = {normalize_book_title(b.title) for b in books}
         
         missing = []
         for work in info.works:
             norm_work = normalize_book_title(work)
             if norm_work and norm_work not in owned:
                 is_owned = False
                 for ot in owned:
                     if ot and (ot in norm_work or norm_work in ot):
                         is_owned = True; break
                 if not is_owned: missing.append(work)
         return sorted(list(set(missing)))
    except Exception as e:
        log.error("Failed missing books check: %s", e)
        return []

def get_series_works(series_name, author_names=None):
    """Global series lookup using Open Library search."""
    try:
        search_url = f'{OPENLIBRARY_BASE}/search.json?q={series_name}'
        resp = requests.get(search_url, timeout=API_TIMEOUT)
        data = resp.json()
        works = []
        auth_set = {a.lower().strip() for a in author_names} if author_names else set()
        
        for doc in data.get('docs', []):
            title = doc.get('title')
            doc_auths = [a.lower().strip() for a in doc.get('author_name', [])]
            if auth_set and not any(a in auth_set for a in doc_auths): continue
            
            norm_title = normalize_book_title(title)
            norm_series = normalize_book_title(series_name)
            
            is_cand = norm_series in norm_title
            if not is_cand:
                doc_series = [normalize_book_title(s) for s in doc.get('series', [])]
                if norm_series in doc_series: is_cand = True
            
            if is_cand: works.append(title)
        return sorted(list(set(works)))
    except: return []

def get_author_works(author_name, limit=100):
    """Direct author bibliography lookup."""
    try:
        ol = OpenLibrarySource()
        res = ol.fetch(author_name)
        return res['works'] if res else []
    except: return []
