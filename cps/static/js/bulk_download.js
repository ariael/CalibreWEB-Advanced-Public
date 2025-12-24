/**
 * Bulk Download Handler with Progress Tracking
 * Handles author/series bulk downloads with inline progress and automatic download
 */

class BulkDownloadHandler {
    constructor() {
        this.activeDownloads = new Map();
        this.pollInterval = 2000; // Poll every 2 seconds
    }

    /**
     * Start a bulk download
     * @param {string} url - The download initiation URL
     * @param {HTMLElement} button - The download button element
     * @param {string} type - 'author' or 'series'
     */
    async startDownload(url, button, type = 'author') {
        // Disable button and show inline progress
        const originalHTML = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<span class="glyphicon glyphicon-hourglass"></span> <span class="download-progress-text">0%</span>';
        button.classList.add('btn-downloading');

        try {
            // Make AJAX request to start download task
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to start download');
            }

            const data = await response.json();

            if (data.task_id) {
                // Show toast notification
                window.toastNotification.show(
                    data.message || 'Preparing ZIP file...',
                    'download',
                    0, // Persistent
                    `download-${data.task_id}`
                );

                // Start polling for progress
                this.pollTaskStatus(data.task_id, button, originalHTML, type);
            } else {
                throw new Error('No task ID returned');
            }
        } catch (error) {
            console.error('Download error:', error);
            button.disabled = false;
            button.innerHTML = originalHTML;
            button.classList.remove('btn-downloading');

            window.toastNotification.show(
                'Failed to start download: ' + error.message,
                'error',
                5000
            );
        }
    }

    /**
     * Poll task status and update progress
     * @param {string} taskId - The task ID to poll
     * @param {HTMLElement} button - The download button
     * @param {string} originalHTML - Original button HTML
     * @param {string} type - Download type
     */
    async pollTaskStatus(taskId, button, originalHTML, type) {
        const pollerId = setInterval(async () => {
            try {
                const response = await fetch(`/ajax/task-status/${taskId}`);

                if (!response.ok) {
                    throw new Error('Failed to get task status');
                }

                const data = await response.json();

                // Update inline progress
                const progressText = button.querySelector('.download-progress-text');
                if (progressText && data.progress !== undefined) {
                    const percent = Math.round(data.progress * 100);
                    progressText.textContent = `${percent}%`;
                }

                // Update toast notification
                if (data.progress !== undefined) {
                    const percent = Math.round(data.progress * 100);
                    window.toastNotification.update(
                        `download-${taskId}`,
                        `Creating ZIP file... ${percent}%`,
                        'download'
                    );
                }

                // Check if completed
                if (data.status === 'completed' || data.status === 'finished') {
                    clearInterval(pollerId);
                    this.handleDownloadComplete(taskId, data, button, originalHTML);
                } else if (data.status === 'failed' || data.status === 'error') {
                    clearInterval(pollerId);
                    this.handleDownloadError(taskId, data, button, originalHTML);
                }
            } catch (error) {
                console.error('Polling error:', error);
                clearInterval(pollerId);
                this.handleDownloadError(taskId, { error: error.message }, button, originalHTML);
            }
        }, this.pollInterval);

        // Store poller ID for potential cancellation
        this.activeDownloads.set(taskId, pollerId);
    }

    /**
     * Handle successful download completion
     */
    handleDownloadComplete(taskId, data, button, originalHTML) {
        // Reset button
        button.disabled = false;
        button.innerHTML = originalHTML;
        button.classList.remove('btn-downloading');

        // Update toast to success
        window.toastNotification.update(
            `download-${taskId}`,
            'ZIP file ready! Download starting...',
            'success'
        );

        // Trigger automatic download
        if (data.download_url) {
            this.triggerDownload(data.download_url);

            // Remove toast after download starts
            setTimeout(() => {
                window.toastNotification.remove(`download-${taskId}`);
            }, 3000);
        } else {
            window.toastNotification.update(
                `download-${taskId}`,
                'ZIP file ready! Click to download.',
                'success'
            );
        }

        // Clean up
        this.activeDownloads.delete(taskId);
    }

    /**
     * Handle download error
     */
    handleDownloadError(taskId, data, button, originalHTML) {
        // Reset button
        button.disabled = false;
        button.innerHTML = originalHTML;
        button.classList.remove('btn-downloading');

        // Show error toast
        window.toastNotification.update(
            `download-${taskId}`,
            'Download failed: ' + (data.error || 'Unknown error'),
            'error'
        );

        // Remove error toast after 5 seconds
        setTimeout(() => {
            window.toastNotification.remove(`download-${taskId}`);
        }, 5000);

        // Clean up
        this.activeDownloads.delete(taskId);
    }

    /**
     * Trigger file download
     */
    triggerDownload(url) {
        const a = document.createElement('a');
        a.href = url;
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    /**
     * Cancel an active download
     */
    cancelDownload(taskId) {
        const pollerId = this.activeDownloads.get(taskId);
        if (pollerId) {
            clearInterval(pollerId);
            this.activeDownloads.delete(taskId);
            window.toastNotification.remove(`download-${taskId}`);
        }
    }
}

// Global instance
window.bulkDownloadHandler = new BulkDownloadHandler();

/**
 * Helper function to attach to download buttons
 */
function initBulkDownloadButtons() {
    // Author download buttons
    document.querySelectorAll('a[href*="/author/bulk-download/"]').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            window.bulkDownloadHandler.startDownload(this.href, this, 'author');
        });
    });

    // Series download buttons
    document.querySelectorAll('a[href*="/series/bulk-download/"]').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            window.bulkDownloadHandler.startDownload(this.href, this, 'series');
        });
    });
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBulkDownloadButtons);
} else {
    initBulkDownloadButtons();
}
