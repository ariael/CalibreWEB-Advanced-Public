from flask_babel import lazy_gettext as N_
from datetime import datetime, timezone
import time

from cps import logger, ub, db, audit_helper, config, app
from cps.services.worker import CalibreTask, STAT_CANCELLED, STAT_ENDED


class TaskRefreshAuthorDashboard(CalibreTask):
    def __init__(self, task_message=N_('Updating Author Dashboard Health Cache')):
        super(TaskRefreshAuthorDashboard, self).__init__(task_message)
        self.log = logger.create()
        self.app_db_session = ub.get_new_session_instance()

    def run(self, worker_thread):
        try:
            with app.app_context():
                calibre_db = db.CalibreDB(app)
                # Get existing health entries to check for incremental update
                health_entries = {h.book_id: h.last_scan for h in self.app_db_session.query(ub.BookHealth).all()}
                
                # Get all books from calibre database
                all_books = calibre_db.session.query(db.Books).all()
                
                # Filter books that actually need scanning
                books_to_scan = []
                for book in all_books:
                    last_scan = health_entries.get(book.id)
                    # Scan if never scanned, or if book was modified after last scan
                    if not last_scan or book.last_modified > last_scan:
                        books_to_scan.append(book)
                
                total = len(books_to_scan)
                self.log.info("Starting incremental health refresh for %d books (skipped %d)", 
                             total, len(all_books) - total)

                if total == 0:
                    self.log.info("No books need health refresh")
                    self.progress = 1.0
                    self.app_db_session.commit()
                    self._handleSuccess()
                    return

                for index, book in enumerate(books_to_scan):
                    if self.stat == STAT_CANCELLED or self.stat == STAT_ENDED:
                        self.log.info("Health refresh task cancelled")
                        return

                    # Calculate health
                    health = audit_helper.get_book_health(book, config.get_book_path(), quick=True)

                    # Update or create cache entry in app.db
                    health_cache = self.app_db_session.query(ub.BookHealth).filter(ub.BookHealth.book_id == book.id).first()
                    if not health_cache:
                        health_cache = ub.BookHealth(book_id=book.id)
                        self.app_db_session.add(health_cache)
                    
                    health_cache.is_healthy = health['is_healthy']
                    health_cache.has_azw = health['has_azw']
                    health_cache.has_epub = health['has_epub']
                    health_cache.has_docx_cz = health['has_docx_cz']
                    health_cache.extra_formats = health['extra_formats']
                    health_cache.desc_lang = health['desc_lang']
                    health_cache.last_scan = datetime.now(timezone.utc)

                    # Periodic commit for progress
                    if index % 20 == 0:
                        try:
                            self.app_db_session.commit()
                            self.progress = (index + 1) / total
                            self.message = N_('Processed %(count)d of %(total)d books', count=index+1, total=total)
                        except Exception as e:
                            self.log.error("Failed to commit health cache: %s", e)
                            self.app_db_session.rollback()
                        
                        # Throttle slightly
                        time.sleep(0.05)

                self.app_db_session.commit()
                self._handleSuccess()
                self.log.info("Background health refresh completed")
        except Exception as ex:
            self.log.error("Error during background health refresh: %s", ex)
            self._handleError(str(ex))
            self.app_db_session.rollback()
        finally:
            self.app_db_session.remove()

    @property
    def name(self):
        return "Refresh Author Dashboard"

    def __str__(self):
        return "TaskRefreshAuthorDashboard"

    @property
    def is_cancellable(self):
        return True
