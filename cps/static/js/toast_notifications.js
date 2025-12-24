/**
 * Toast Notification System for Calibre-Web
 * Provides non-blocking notifications for background tasks
 */

class ToastNotification {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create toast container if it doesn't exist
        if (!document.getElementById('toast-container')) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('toast-container');
        }
    }

    /**
     * Show a toast notification
     * @param {string} message - The message to display
     * @param {string} type - Type: 'info', 'success', 'warning', 'error'
     * @param {number} duration - Duration in ms (0 = persistent)
     * @param {string} id - Optional unique ID for the toast
     */
    show(message, type = 'info', duration = 5000, id = null) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        if (id) {
            toast.id = `toast-${id}`;
            // Remove existing toast with same ID
            const existing = document.getElementById(`toast-${id}`);
            if (existing) {
                existing.remove();
            }
        }

        const icon = this.getIcon(type);
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-message">${message}</div>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;

        this.container.appendChild(toast);

        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);

        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        return toast;
    }

    /**
     * Update an existing toast
     * @param {string} id - Toast ID
     * @param {string} message - New message
     * @param {string} type - New type (optional)
     */
    update(id, message, type = null) {
        const toast = document.getElementById(`toast-${id}`);
        if (toast) {
            const messageEl = toast.querySelector('.toast-message');
            if (messageEl) {
                messageEl.textContent = message;
            }
            if (type) {
                toast.className = `toast toast-${type} show`;
                const iconEl = toast.querySelector('.toast-icon');
                if (iconEl) {
                    iconEl.innerHTML = this.getIcon(type);
                }
            }
        }
    }

    /**
     * Remove a toast by ID
     * @param {string} id - Toast ID
     */
    remove(id) {
        const toast = document.getElementById(`toast-${id}`);
        if (toast) {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }
    }

    getIcon(type) {
        const icons = {
            'info': '<span class="glyphicon glyphicon-info-sign"></span>',
            'success': '<span class="glyphicon glyphicon-ok-sign"></span>',
            'warning': '<span class="glyphicon glyphicon-warning-sign"></span>',
            'error': '<span class="glyphicon glyphicon-exclamation-sign"></span>',
            'download': '<span class="glyphicon glyphicon-download-alt"></span>'
        };
        return icons[type] || icons['info'];
    }
}

// Global instance
window.toastNotification = new ToastNotification();
