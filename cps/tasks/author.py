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
                    
                    # Fix timestamp comparison - Force Naive UTC for both
                    if last_scan and last_scan.tzinfo is not None:
                        last_scan = last_scan.replace(tzinfo=None)
                    
                    book_mod = book.last_modified
                    if book_mod and book_mod.tzinfo is not None:
                        book_mod = book_mod.replace(tzinfo=None)

                    # Scan if never scanned, or if book was modified after last scan
                    if not last_scan or book_mod > last_scan:
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
                        self.yield_cpu()

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

class TaskEnrichAuthors(CalibreTask):
    def __init__(self, task_message=N_('Enriching Author Metadata')):
        super(TaskEnrichAuthors, self).__init__(task_message)
        self.log = logger.create()
        self.app_db_session = ub.get_new_session_instance()

    def run(self, worker_thread):
        from cps import services
        try:
            self.log.info("=== TaskEnrichAuthors STARTING ===")
            with app.app_context():
                calibre_db = db.CalibreDB(app)
                
                # Get all authors from library
                all_authors = calibre_db.session.query(db.Authors).all()
                self.log.info("Found %d total authors in library", len(all_authors))
                
                # Get existing enrichment info - use last_checked for scheduling, not last_updated
                existing_info = {}
                for a in self.app_db_session.query(ub.AuthorInfo).all():
                    # Use last_checked if available, fall back to last_updated for migration
                    check_time = getattr(a, 'last_checked', None) or a.last_updated
                    existing_info[a.author_id] = check_time
                
                authors_to_process = []
                new_authors = []
                now = datetime.now(timezone.utc)
                
                skipped_recently_checked = 0
                for author in all_authors:
                    last_checked = existing_info.get(author.id)
                    
                    if not last_checked:
                        # New author - never fetched
                        authors_to_process.append(author)
                        new_authors.append(author.id)
                    else:
                        # Check every 7 days (lighter load than 30 days, but uses hash to avoid writes)
                        if last_checked.tzinfo is None:
                            last_checked = last_checked.replace(tzinfo=timezone.utc)
                        days_since_check = (now - last_checked).days
                        if days_since_check >= 7:
                            authors_to_process.append(author)
                        else:
                            skipped_recently_checked += 1
                
                total = len(authors_to_process)
                new_count = len(new_authors)
                update_count = total - new_count
                
                self.log.info("Author enrichment: %d to process (%d new, %d refresh), %d recently checked (skipped)", 
                            total, new_count, update_count, skipped_recently_checked)
                
                if total == 0:
                    self.log.info("=== TaskEnrichAuthors COMPLETED: All %d authors recently checked ===", 
                                 len(all_authors))
                    self.progress = 1.0
                    self._handleSuccess()
                    return

                processed = 0
                updated = 0
                
                for index, author in enumerate(authors_to_process):
                    if self.stat == STAT_CANCELLED or self.stat == STAT_ENDED:
                        self.log.info("Task cancelled after processing %d authors", processed)
                        self.app_db_session.commit()
                        return

                    author_name = author.name.replace('|', ',')
                    is_new = author.id in new_authors
                    
                    # Defer commit to the bulk loop
                    services.author_enrichment.get_author_info(
                        author.id, 
                        author_name, 
                        force_refresh=True,
                        is_initial_load=is_new,
                        commit=False
                    )
                    
                    processed += 1
                    updated += 1 # We assume change if force_refresh is on, or we could check hash
                    
                    # Yield CPU and check for cancellation
                    self.yield_cpu()
                    
                    # Be nice to external APIs
                    time.sleep(1)
                    
                    # Batch commit every 10 authors
                    if processed % 10 == 0:
                        self.app_db_session.commit()
                        self.progress = (index + 1) / total
                        self.message = N_('Processed %(count)d of %(total)d authors', 
                                         count=index+1, total=total)

                self.app_db_session.commit()
                self.log.info("=== TaskEnrichAuthors COMPLETED: Processed %d authors ===", processed)
                self._handleSuccess()
                
        except Exception as ex:
            self.log.error("Error during author enrichment: %s", ex)
            self._handleError(str(ex))
        finally:
            self.app_db_session.remove()

    @property
    def name(self):
        return "Enrich Authors"

    def __str__(self):
        return "TaskEnrichAuthors"

    @property
    def is_cancellable(self):
        return True
