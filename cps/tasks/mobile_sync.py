from flask_babel import lazy_gettext as N_
import os
from cps import logger, ub, db, app
from cps.services.worker import CalibreTask, STAT_CANCELLED, STAT_ENDED
from cps.mobile import auto_sync_mobile_progress

class TaskMobileSync(CalibreTask):
    def __init__(self, task_message=N_('Synchronizing Mobile App Progress')):
        super(TaskMobileSync, self).__init__(task_message)
        self.log = logger.create()

    def run(self, worker_thread):
        try:
            self.log.info("Starting background mobile progress sync")
            with app.app_context():
                auto_sync_mobile_progress()
            self._handleSuccess()
            self.log.info("Background mobile progress sync completed")
        except Exception as ex:
            self.log.error("Error during mobile progress sync: %s", ex)
            self._handleError(str(ex))

    @property
    def name(self):
        return "Mobile Sync"

    def __str__(self):
        return "TaskMobileSync"

    @property
    def is_cancellable(self):
        return True
