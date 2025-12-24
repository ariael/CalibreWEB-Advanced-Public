# -*- coding: utf-8 -*-

import os
import zipfile
from datetime import datetime
from flask_babel import lazy_gettext as N_
from cps.services.worker import CalibreTask, STAT_FINISH_SUCCESS, STAT_STARTED, STAT_FAIL, STAT_ENDED, STAT_CANCELLED
from cps import config, db, app, logger

log = logger.create()

class TaskBulkDownload(CalibreTask):
    def __init__(self, task_message, book_ids, zip_filename, user_id):
        super(TaskBulkDownload, self).__init__(task_message)
        self.book_ids = book_ids
        self.zip_filename = zip_filename
        self.user_id = user_id
        self.progress = 0
        self.zip_path = None
        log.debug_tag("ZIP", "TaskBulkDownload.__init__: Created task for %d books, ZIP: %s", len(book_ids), zip_filename)

    def run(self, worker_thread):
        log.debug_tag("ZIP", "run() method called with %d book IDs", len(self.book_ids))
        self.stat = STAT_STARTED
        # Use a subfolder in the cache or temp dir
        tmp_dir = os.path.join(config.config_calibre_dir, "downloads")
        log.debug_tag("ZIP", "tmp_dir = %s", tmp_dir)
        if not os.path.exists(tmp_dir):
            try:
                os.makedirs(tmp_dir)
                log.debug_tag("ZIP", "Created directory %s", tmp_dir)
            except OSError as e:
                log.error("Failed to create download directory: %s", e)
                return

        self.zip_path = os.path.join(tmp_dir, self.zip_filename)
        
        log.debug_tag("ZIP", "Task started for %d books, ZIP: %s", len(self.book_ids), self.zip_path)
        
        with app.app_context():
            # Use the app's db instance if available or create a new one
            worker_db = db.CalibreDB(app)
            log.info("Bulk Download: Starting ZIP creation for %d books", len(self.book_ids))
            try:
                with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    total = len(self.book_ids)
                    files_added = 0
                    for i, book_id in enumerate(self.book_ids):
                        if self.stat in (STAT_ENDED, STAT_CANCELLED):
                            log.info("Bulk Download: Stopped/Cancelled by user")
                            break
                        book = worker_db.get_book(book_id)
                        if not book:
                            log.debug_tag("ZIP", "Book ID %d not found", book_id)
                            continue
                        if not book.data:
                            log.debug_tag("ZIP", "Book ID %d has no data/formats", book_id)
                            continue
                            
                        # Prefer EPUB if available, otherwise first format
                        data = None
                        for d in book.data:
                            if d.format.upper() == 'EPUB':
                                data = d
                                break
                        if not data:
                            data = book.data[0]
                        
                        file_path = os.path.join(config.get_book_path(), book.path, data.name + "." + data.format.lower())
                        if os.path.exists(file_path):
                            zipf.write(file_path, arcname=os.path.join(book.path, data.name + "." + data.format.lower()))
                            files_added += 1
                            log.debug_tag("ZIP", "Added %s", file_path)
                        else:
                            log.debug_tag("ZIP", "File not found: %s", file_path)
                        self.progress = (i + 1) / total
                    log.info("Bulk Download: Completed - added %d files out of %d books", files_added, total)
                self.stat = STAT_FINISH_SUCCESS
            except Exception as e:
                log.error("Bulk Download failed: %s", e, exc_info=True)
                self.stat = STAT_FAIL

    @property
    def name(self):
        return N_("Bulk Download")

    def __str__(self):
        result = "Zipping {} books into {}".format(len(self.book_ids), self.zip_filename)
        log.debug("TaskBulkDownload.__str__: %s", result)
        return result

    @property
    def is_cancellable(self):
        return True
