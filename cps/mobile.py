# -*- coding: utf-8 -*-

import json
import os
import zipfile
import subprocess
import tempfile
import sqlite3
from flask import Blueprint, request, flash, redirect, url_for
from flask_babel import gettext as _
from flask_login import login_required, current_user
from sqlalchemy import and_
from . import db, ub, helper, calibre_db

mobile = Blueprint('mobile', __name__, url_prefix='/mobile')

@mobile.route('/upload_progress', methods=['POST'])
@login_required
def upload_progress():
    if 'file' not in request.files:
        flash(_('No file part'), 'error')
        return redirect(url_for('web.profile'))
    
    file = request.files['file']
    app_type = request.form.get('app_type', 'librera')
    
    if file.filename == '':
        flash(_('No selected file'), 'error')
        return redirect(url_for('web.profile'))

    # Save to temp file
    fd, path = tempfile.mkstemp()
    try:
        os.close(fd)
        file.save(path)
        
        count = 0
        if app_type == 'librera':
            with open(path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                count = process_librera_progress(content)
        elif app_type == 'moon':
            count = process_moon_progress(path)
        elif app_type == 'readera':
            count = process_readera_progress(path)
        else:
            flash(_('Unknown app type'), 'error')
            return redirect(url_for('web.profile'))
            
        flash(_('Successfully updated progress for %(count)d books', count=count), 'success')
            
    except Exception as e:
        flash(_('Error processing file: %(error)s', error=str(e)), 'error')
    finally:
        if os.path.exists(path):
            os.remove(path)

    return redirect(url_for('web.profile'))

@mobile.route('/sync_usb_progress', methods=['POST'])
@login_required
def sync_usb_progress():
    app_type = request.form.get('app_type', 'librera')
    
    # 1. Check for devices
    try:
        devices_out = subprocess.check_output(['adb', 'devices'], stderr=subprocess.STDOUT).decode('utf-8')
        lines = [line for line in devices_out.splitlines() if line.strip() and '\tdevice' in line]
        if not lines:
            flash(_('No Android device connected via ADB.'), 'error')
            return redirect(url_for('web.profile'))
    except Exception:
        flash(_('ADB not found or error listing devices.'), 'error')
        return redirect(url_for('web.profile'))

    updated_count = 0
    found_file = False
    
    try:
        if app_type == 'librera':
            updated_count, found_file = sync_librera_usb()
        elif app_type == 'moon':
            updated_count, found_file = sync_moon_usb()
        elif app_type == 'readera':
            updated_count, found_file = sync_readera_usb()
        
        if found_file:
             flash(_('Successfully synchronized %(count)d books from USB device (%(app)s).', count=updated_count, app=app_type.capitalize()), 'success')
        else:
             flash(_('Could not find progress file for %(app)s on device.', app=app_type.capitalize()), 'error')
             
    except Exception as e:
        flash(_('ADB Error: %(error)s', error=str(e)), 'error')

    return redirect(url_for('web.profile'))

def sync_librera_usb():
    base_path = '/sdcard/Librera/profile.Librera/'
    ls_out = subprocess.check_output(['adb', 'shell', 'ls', base_path], stderr=subprocess.STDOUT).decode('utf-8')
    profile_folders = [f.strip() for f in ls_out.splitlines() if f.strip().startswith('device.')]
    
    count = 0
    found = False
    
    for folder in profile_folders:
        remote_path = f"{base_path}{folder}/app-Progress.json"
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            local_path = tmp.name
        try:
            subprocess.check_call(['adb', 'pull', remote_path, local_path], stderr=subprocess.DEVNULL)
            if os.path.getsize(local_path) > 0:
                with open(local_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    c = process_librera_progress(data)
                    count += c
                    found = True
        except: pass
        finally:
            if os.path.exists(local_path): os.remove(local_path)
    return count, found

def sync_moon_usb():
    # Moon+ Reader backups are usually in /sdcard/Books/MoonReader/ or user defined.
    # We search for .mrpro files in likely locations.
    search_paths = ['/sdcard/Books/MoonReader/', '/sdcard/Books/']
    
    # We can try to list files with .mrpro extension using find or ls
    # using simple ls for likely paths
    
    candidate_files = []
    
    for path in search_paths:
        try:
            out = subprocess.check_output(['adb', 'shell', 'ls', path], stderr=subprocess.STDOUT).decode('utf-8')
            for line in out.splitlines():
                if line.strip().endswith('.mrpro') or line.strip().endswith('.po'):
                    candidate_files.append(path + line.strip())
        except: pass
        
    if not candidate_files:
        return 0, False
        
    # Sort by recent? ADB ls doesn't give dates easily unless we use ls -l
    # Just grab the first one or latest one if possible. 
    # For now, let's process the first one found.
    
    remote_path = candidate_files[0]
    count = 0
    found = False
    
    with tempfile.NamedTemporaryFile(suffix='.mrpro', delete=False) as tmp:
         local_path = tmp.name
         
    try:
        subprocess.check_call(['adb', 'pull', remote_path, local_path], stderr=subprocess.DEVNULL)
        if os.path.getsize(local_path) > 0:
            count = process_moon_progress(local_path)
            found = True
    except: pass
    finally:
        if os.path.exists(local_path): os.remove(local_path)
            
    return count, found

def sync_readera_usb():
    # ReadEra doesn't have a default "auto sync" folder, backups are manual.
    # We search /sdcard/ReadEra/ (if exists) or /sdcard/ for .bak files? Too broad.
    # Most likely user saves them to Download or default path.
    # Let's try /sdcard/ReadEra/ and /sdcard/Download/
    
    search_paths = ['/sdcard/ReadEra/', '/sdcard/Download/']
    candidate_files = []
    
    for path in search_paths:
        try:
            out = subprocess.check_output(['adb', 'shell', 'ls', path], stderr=subprocess.STDOUT).decode('utf-8')
            for line in out.splitlines():
                if line.strip().endswith('.bak'):
                    candidate_files.append(path + line.strip())
        except: pass
        
    if not candidate_files:
        return 0, False
        
    remote_path = candidate_files[0] # Pick first found
    count = 0
    found = False
    
    with tempfile.NamedTemporaryFile(suffix='.bak', delete=False) as tmp:
        local_path = tmp.name
        
    try:
        subprocess.check_call(['adb', 'pull', remote_path, local_path], stderr=subprocess.DEVNULL)
        if os.path.getsize(local_path) > 0:
            count = process_readera_progress(local_path)
            found = True
    except: pass
    finally:
        if os.path.exists(local_path): os.remove(local_path)
            
    return count, found


def process_librera_progress(data, user=None):
    count = 0
    from datetime import datetime
    for file_path, progress_data in data.items():
        if not isinstance(progress_data, dict): continue
        progress_ratio = progress_data.get('p', 0)
        percentage = int(progress_ratio * 100)
        percentage = max(0, min(100, percentage))
        if percentage == 0: continue
        
        filename = os.path.basename(file_path)
        base_name, _ = os.path.splitext(filename)
        if update_book_progress(base_name, percentage, user):
            count += 1
    ub.session.commit()
    return count

def process_moon_progress(file_path, user=None):
    count = 0
    import zipfile
    import sqlite3
    import tempfile
    import shutil
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
                
            # Moon+ Reader backups usually contain a .db file
            db_file = None
            for root, dirs, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith('.db'):
                        db_file = os.path.join(root, f)
                        break
                if db_file: break
                
            if db_file:
                # Some versions use 'items' table, some 'books'
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Check for table 'items' (Moon+ Reader Pro standard)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='items' OR name='books')")
                table_name = cursor.fetchone()
                if table_name:
                    table = table_name[0]
                    # Columns: originalName (or filename), percentage
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = {col[1] for col in cursor.fetchall()}
                    
                    name_col = "originalName" if "originalName" in columns else "filename" if "filename" in columns else "title"
                    perc_col = "percentage" if "percentage" in columns else "progress"
                    
                    if name_col in columns and perc_col in columns:
                        cursor.execute(f"SELECT {name_col}, {perc_col} FROM {table}")
                        rows = cursor.fetchall()
                        for name, percentage in rows:
                            if percentage and percentage > 0:
                                # percentage is usually float 0-100 or int
                                p = int(float(percentage))
                                if update_book_progress(name, p, user):
                                    count += 1
                conn.close()
        except Exception as e:
            helper.log.error(f"Error parsing Moon+ Reader backup: {e}")
            
    ub.session.commit()
    return count

def process_readera_progress(file_path, user=None):
    count = 0
    import zipfile
    import json
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
            
            json_path = os.path.join(tmpdir, 'library.json')
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # ReadEra 'books' list
                    books_data = data.get('books', [])
                    for b in books_data:
                        # title, author, reading_percentage
                        title = b.get('title')
                        author = b.get('author')
                        percentage = b.get('reading_percentage', 0)
                        
                        search_name = f"{title} - {author}" if author else title
                        if percentage > 0:
                            if update_book_progress(search_name, int(percentage), user):
                                count += 1
        except Exception as e:
            helper.log.error(f"Error parsing ReadEra backup: {e}")
            
    ub.session.commit()
    return count

def update_book_progress(search_name, percentage, user=None):
    # Clean name: remove extensions, underscores, and common Calibre-style segments
    search_name = search_name.replace('_', ' ').strip()
    for ext in ['.epub', '.mobi', '.azw3', '.pdf', '.docx', '.html', '.txt']:
        if search_name.lower().endswith(ext):
            search_name = search_name[:-len(ext)].strip()
            
    # Try extracting Calibre ID from name if it follows "Title (ID)" pattern
    import re
    id_match = re.search(r'\((\d+)\)$', search_name)
    if id_match:
        book_id = int(id_match.group(1))
        book = calibre_db.session.query(db.Books).filter(db.Books.id == book_id).first()
        if book:
            books = [book]
            
    # Try exact match first
    if not books:
        books = calibre_db.session.query(db.Books).filter(db.Books.title.ilike(search_name)).all()
    
    # Try splitting if it's "Title - Author" format
    if not books and ' - ' in search_name:
        parts = search_name.split(' - ')
        # Try title part
        books = calibre_db.session.query(db.Books).filter(db.Books.title.ilike(parts[0].strip())).all()
        # If still no, try matching both Title AND Author for precision
        if not books and len(parts) > 1:
            books = calibre_db.session.query(db.Books).join(db.books_authors_link).join(db.Authors).filter(
                and_(db.Books.title.ilike(parts[0].strip()), db.Authors.name.ilike(f"%{parts[1].strip()}%"))
            ).all()
            
    if books:
        book = books[0]
        # Fallback to current_user if no specific user provided (for manual uploads)
        target_user = user or current_user
        if not target_user:
            return False

        current_status = ub.session.query(ub.ReadBook).filter(
            ub.ReadBook.user_id == target_user.id,
            ub.ReadBook.book_id == book.id
        ).first()
        
        if not current_status:
            current_status = ub.ReadBook(user_id=target_user.id, book_id=book.id)
            ub.session.add(current_status)
        
        status = ub.ReadBook.STATUS_IN_PROGRESS
        if percentage >= 99:
             status = ub.ReadBook.STATUS_FINISHED
             percentage = 100
        
        current_status.progress_percent = percentage
        current_status.read_status = status
        from datetime import datetime
        current_status.last_modified = datetime.utcnow()
        return True
    return False
def auto_sync_mobile_progress():
    """Background task to scan user-defined folders for progress files"""
    users = ub.session.query(ub.User).filter(ub.User.mobile_sync_path != "").all()
    for user in users:
        path = user.mobile_sync_path
        if not os.path.isdir(path):
            continue
            
        helper.log.debug(f"Auto-sync: Scanning {path} for user {user.name}")
        
        # 1. Librera (app-Progress.json)
        # Search recursively or in known subpaths
        for root, dirs, files in os.walk(path):
            for f in files:
                f_path = os.path.join(root, f)
                
                # Librera
                if f == 'app-Progress.json':
                    try:
                        with open(f_path, 'r', encoding='utf-8') as jf:
                            process_librera_progress(json.load(jf), user)
                    except: pass
                
                # Moon+ (.mrpro or .po)
                elif f.endswith('.mrpro'):
                    process_moon_progress(f_path, user)
                
                # ReadEra (.bak)
                elif f.endswith('.bak'):
                    process_readera_progress(f_path, user)
    
    ub.session.commit()
