# -*- coding: utf-8 -*-
import os
import shutil
from sqlalchemy import func
from . import db, calibre_db, helper, logger

log = logger.create()

def rename_author_global(author_id, new_name, calibre_path):
    if not new_name or not new_name.strip():
        return False, "New name cannot be empty"

    author = calibre_db.session.query(db.Authors).get(author_id)
    if not author:
        return False, "Author not found"

    old_author_name = author.name
    new_name = new_name.strip()

    if old_author_name == new_name:
        return True, "No change needed"

    # 1. Update author name and sort in database
    author.name = new_name
    author.sort = helper.get_sorted_author(new_name.replace('|', ','))

    # 2. Update all books associated with this author
    all_books = calibre_db.session.query(db.Books) \
        .filter(db.Books.authors.any(db.Authors.id == author_id)).all()

    sorted_old_author = helper.get_sorted_author(old_author_name)
    sorted_new_author = author.sort

    for book in all_books:
        # Update author_sort if it contains the old author
        if book.author_sort:
            book.author_sort = book.author_sort.replace(sorted_old_author, sorted_new_author)

        # Handle path renaming if this was the first author
        # book.path usually starts with "Author/Title (id)"
        parts = book.path.split('/')
        if len(parts) >= 2:
            old_author_dir = parts[0]
            # Check if this book's path actually starts with the old author's directory name
            # Note: Calibre uses a sanitized version of the author name for the directory
            expected_old_dir = helper.get_valid_filename(old_author_name, chars=96)
            if old_author_dir.lower() == expected_old_dir.lower():
                try:
                    new_author_dir = helper.rename_author_path(new_name, old_author_dir, old_author_name, calibre_path)
                    book.path = os.path.join(new_author_dir, parts[1]).replace('\\', '/')
                    
                    # Also rename files inside the folder if they follow the "Title - Author" convention
                    new_full_path = os.path.join(calibre_path, book.path)
                    new_file_prefix = helper.get_valid_filename(book.title, chars=42) + ' - ' + helper.get_valid_filename(new_name, chars=42)
                    helper.rename_all_files_on_change(book, new_full_path, new_full_path, new_file_prefix)
                except Exception as e:
                    log.error("Failed to rename files for book %d during author rename: %s", book.id, e)

    try:
        calibre_db.session.commit()
        return True, "Author renamed successfully"
    except Exception as e:
        calibre_db.session.rollback()
        log.error("Failed to commit author rename: %s", e)
        return False, str(e)

def rename_series_global(series_id, new_name):
    if not new_name or not new_name.strip():
        return False, "New name cannot be empty"

    series = calibre_db.session.query(db.Series).get(series_id)
    if not series:
        return False, "Series not found"

    series.name = new_name.strip()
    series.sort = series.name

    try:
        calibre_db.session.commit()
        return True, "Series renamed successfully"
    except Exception as e:
        calibre_db.session.rollback()
        return False, str(e)
