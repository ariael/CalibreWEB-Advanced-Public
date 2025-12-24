# -*- coding: utf-8 -*-

from flask_babel import lazy_gettext as N_
from cps import helper, config, logger, app
from cps.services.worker import CalibreTask

log = logger.create()

class TaskUpdateMetadata(CalibreTask):
    def __init__(self, book_id, first_author=None):
        super(TaskUpdateMetadata, self).__init__(N_("Updating book metadata and files"))
        self.book_id = book_id
        self.first_author = first_author

    def run(self, worker_thread):
        with app.app_context():
            log.debug("Background metadata update for book %s", self.book_id)
            error = helper.update_dir_structure(self.book_id,
                                             config.get_book_path(),
                                             self.first_author)
            if error:
                log.error("Background metadata update failed: %s", error)
                self._handleError(error)
            else:
                self._handleSuccess()

    @property
    def name(self):
        return N_("Update Metadata")

    @property
    def is_cancellable(self):
        return False
