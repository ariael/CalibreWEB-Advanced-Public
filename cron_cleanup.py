#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Calibre-Web Maintenance Script
- Cleans orphaned files in the library
- Checks database integrity
- Cleans up temporary files
"""

import os
import sys
import shutil
from sqlalchemy import create_engine, text

# Ensure we can import from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from cps import config_sql, logger
except ImportError:
    print("Error: Could not import Calibre-Web components. Run this script from the project root.")
    sys.exit(1)

log = logger.create()

def cleanup_library(library_path, dry_run=True):
    if not os.path.exists(library_path):
        print(f"Error: Library path {library_path} does not exist.")
        return

    db_path = os.path.join(library_path, "metadata.db")
    if not os.path.exists(db_path):
        print(f"Error: metadata.db not found at {db_path}")
        return

    print(f"Connecting to {db_path}...")
    engine = create_engine(f'sqlite:///{db_path}')
    
    try:
        with engine.connect() as conn:
            # Get all valid book paths from the database
            res = conn.execute(text("SELECT path FROM books"))
            valid_paths = {row[0].replace('/', os.sep) for row in res}
            
            # Check integrity
            integrity = conn.execute(text("PRAGMA integrity_check")).scalar()
            print(f"Database Integrity Check: {integrity}")
    except Exception as e:
        print(f"Failed to query database: {e}")
        return

    print(f"Scanning for orphans in {library_path}...")
    orphaned_dirs = []
    orphaned_files = []

    # Calibre library structure: Library/Author/BookTitle (ID)/files
    for author_dir in os.listdir(library_path):
        author_path = os.path.join(library_path, author_dir)
        if not os.path.isdir(author_path) or author_dir.startswith('.'):
            continue

        for book_dir in os.listdir(author_path):
            book_path = os.path.join(author_dir, book_dir)
            full_book_path = os.path.join(author_path, book_dir)
            
            if not os.path.isdir(full_book_path):
                continue
                
            if book_path not in valid_paths:
                orphaned_dirs.append(full_book_path)

    if not orphaned_dirs:
        print("No orphaned directories found.")
    else:
        print(f"Found {len(orphaned_dirs)} orphaned directories.")
        for d in orphaned_dirs:
            if dry_run:
                print(f"[DRY RUN] Would delete orphaned directory: {d}")
            else:
                print(f"Deleting orphaned directory: {d}")
                try:
                    shutil.rmtree(d)
                except Exception as e:
                    print(f"Error deleting {d}: {e}")

        # Clean up empty author directories
        for author_dir in os.listdir(library_path):
            author_path = os.path.join(library_path, author_dir)
            if os.path.isdir(author_path) and not os.listdir(author_path):
                if dry_run:
                    print(f"[DRY RUN] Would delete empty author directory: {author_path}")
                else:
                    print(f"Deleting empty author directory: {author_path}")
                    os.rmdir(author_path)

def cleanup_temp():
    # Attempt to find Calibre-Web temp directory
    # Usually in the system temp or configured path
    import tempfile
    temp_root = tempfile.gettempdir()
    cw_temp_prefix = "calibreweb_"
    
    print(f"Cleaning temp files in {temp_root}...")
    for item in os.listdir(temp_root):
        if item.startswith(cw_temp_prefix):
            full_path = os.path.join(temp_root, item)
            try:
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.remove(full_path)
                print(f"Deleted temp item: {item}")
            except Exception as e:
                print(f"Error deleting temp item {item}: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Calibre-Web Maintenance Script')
    parser.add_argument('--force', action='store_true', help='Actually delete files (default is dry run)')
    parser.add_argument('--config', metavar='path', help='Path to app.db settings file')
    args = parser.parse_args()

    # Try to load library path from config
    settings_path = args.config or os.path.join(os.path.dirname(__file__), "app.db")
    if os.path.exists(settings_path):
        print(f"Loading configuration from {settings_path}...")
        # Mocking minimal environment for config_sql
        os.environ['CALIBRE_DB_PATH'] = settings_path
        try:
            from cps import ub
            ub.init_db(settings_path)
            config = config_sql.get_config()
            lib_path = config.get_book_path()
            if lib_path:
                cleanup_library(lib_path, dry_run=not args.force)
            else:
                print("Could not retrieve library path from config.")
        except Exception as e:
            print(f"Error loading config: {e}")
    else:
        print(f"Settings database not found at {settings_path}. Skipping library cleanup.")

    cleanup_temp()
    print("Maintenance complete.")
