# -*- coding: utf-8 -*-

import os
import shutil
from datetime import datetime
from flask_babel import lazy_gettext as N_
from cps import logger, config, uploader, editbooks, db, helper
from cps.services.worker import CalibreTask

log = logger.create()

class TaskWatchedFolder(CalibreTask):
    def __init__(self):
        super(TaskWatchedFolder, self).__init__(N_("Watched Folder Scan"))
        self.progress = 0

    def run(self, worker_thread):
        log.info("Starting Watched Folder scan")
        libraries = config.config_libraries
        
        # Also include the default library if it has a watched folder
        # (Default library isn't in config_libraries list, it's config_calibre_dir)
        # But wait, where do we store the watched folder for the default library?
        # Maybe we should treat all libraries equally.
        
        all_libs = []
        if config.config_calibre_dir:
            # Check if there's a global watched folder setting or if we should add it to default
            # For now, only handle libraries in config_libraries
            all_libs = libraries

        total_files = 0
        processed_files = 0

        for lib in all_libs:
            watch_path = lib.get('watch')
            if not watch_path or not os.path.exists(watch_path):
                continue
            
            files = [f for f in os.listdir(watch_path) if os.path.isfile(os.path.join(watch_path, f))]
            total_files += len(files)

        if total_files == 0:
            self.progress = 1
            log.info("No files found in watched folders")
            return

        from cps import calibre_db
        
        # Save original session if any (unlikely in background)
        # We will manually manage connections for each library
        
        for lib in all_libs:
            watch_path = lib.get('watch')
            if not watch_path or not os.path.exists(watch_path):
                continue
            
            lib_path = lib.get('path')
            if not lib_path or not os.path.exists(os.path.join(lib_path, "metadata.db")):
                log.warning("Library path invalid for Watched Folder: %s", lib_path)
                continue

            # Create a dedicated session for this library
            lib_session = calibre_db.setup_db(lib_path, calibre_db.app_db_path)
            if not lib_session:
                continue

            files = [f for f in os.listdir(watch_path) if os.path.isfile(os.path.join(watch_path, f))]
            
            for filename in files:
                file_path = os.path.join(watch_path, filename)
                filename_root, file_extension = os.path.splitext(filename)
                
                # Check extension
                allowed_extensions = [ext.strip().lower() for ext in config.config_upload_formats.split(',')]
                if file_extension.lower()[1:] not in allowed_extensions and '*' not in allowed_extensions:
                    continue

                log.info("Processing file from watched folder: %s", filename)
                
                try:
                    # 1. Process Metadata
                    # uploader.process needs a temp file, so we copy it to temp first or just use it directly
                    # since it's already on disk.
                    meta = uploader.process(file_path, filename_root, file_extension, config.config_rarfile_location)
                    
                    # 2. Add to Database
                    # Note: create_book_on_upload uses calibre_db.session and calibre_db globally
                    # This is problematic. We need to temporarily "hack" the global calibre_db
                    
                    # Store old state
                    old_path = calibre_db.config_calibre_dir
                    
                    # Set current library context
                    # We need to ensure calibre_db relative functions use the right session
                    # This might require some refactoring of editbooks.py or temporarily shadowing
                    
                    # For now, let's try to set the global session
                    # WARNING: This is not thread safe if other tasks are running concurrently
                    # but typically background tasks are sequential in the worker thread.
                    
                    # We need to make sure calibre_db.session returns OUR lib_session
                    # But calibre_db.session is a property that uses 'g'. Background threads don't have 'g'.
                    
                    # Let's check how other tasks handle this.
                    # Actually, we can just use lib_session directly if we rewrite the upload logic
                    # or temporarily patch calibre_db.
                    
                    # Better: Temporarily update calibre_db.config_calibre_dir and clear its cache
                    calibre_db.update_config(config, lib_path, calibre_db.app_db_path)
                    
                    # We need to 'mock' g.lib_sql for this thread
                    import flask
                    with flask.Flask(__name__).app_context():
                        flask.g.lib_sql = lib_session
                        # Now create_book_on_upload should work with this session
                        db_book, input_authors, title_dir = editbooks.create_book_on_upload(False, meta)
                        editbooks.move_coverfile(meta, db_book)
                        lib_session.commit()
                    
                    log.info("Successfully added book: %s", db_book.title)
                    
                    # 3. Move/Delete original file
                    processed_dir = os.path.join(watch_path, "processed")
                    os.makedirs(processed_dir, exist_ok=True)
                    shutil.move(file_path, os.path.join(processed_dir, filename))
                    
                except Exception as e:
                    log.error("Failed to process watched file %s: %s", filename, e)
                
                processed_files += 1
                self.progress = processed_files / total_files

            # Reset calibre_db to default
            calibre_db.update_config(config, config.config_calibre_dir, calibre_db.app_db_path)
            lib_session.remove()

        self.progress = 1
        log.info("Watched Folder scan finished")

    @property
    def name(self):
        return N_("Watched Folder Scan")

    def __str__(self):
        return "Watched Folder Scan"

    @property
    def is_cancellable(self):
        return True
