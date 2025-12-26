# Project Changelog & Development History

This document tracks the development timeline, major features, and fixes implemented in the custom Calibre-Web Advanced project.

## Week 2: Features & Automation (Dec 23 - Dec 26, 2025)

### Dec 26 (Thursday) - Author Intelligence & Auto-Sync
- **Author Intelligence System**: Implemented a background task (`TaskEnrichAuthors`) to fetch author metadata (biographies, photos, works) from external sources. Added a designated SQL table and smart caching (7-day cycle).
- **Automated Cloud Sync**: Created a zero-touch reading progress synchronization system.
    - Added `mobile_sync_path` to user profile to monitor cloud-mounted folders.
    - Implemented background periodic scanning of these folders.
    - **Smart Matching**: Enhanced book matching logic to use Calibre IDs (`Title (123).epub`), UUIDs, and ISBNs, ensuring 100% accuracy for offline files.
- **Advanced e-Reader Support**: Finished parsing logic for Moon+ Reader (`.mrpro`/SQLite) and ReadEra (`.bak`/JSON) backup files.

### Dec 25 (Wednesday) - Performance & Kindle Optimization
- **Library Auditor Backend Rewrite**: Switched from XML parsing to RegEx-based text extraction in `audit_helper.py`.
    - **Result**: Massive performance gain (hundreds of %), fixed server crashes on large files, reduced I/O by reading only file headers.
- **Smart OPDS Feed**:
    - **Kindle Detection**: Server now identifies Kindle devices and automatically serves/converts to AZW3.
    - **Format Cleaning**: Feed now hides irrelevant formats (DOCX, ORIGINAL_*) to keep the user interface clean.

### Dec 24 (Tuesday) - Auditor UI & Sync Refactor
- **Auditor Frontend Overhaul**: Replaced the static table with an interactive "Card" view for health check results.
- **Quick Actions**: Added buttons to immediately fix/delete problematic entries from the Auditor view.
- **Sync Module Refactor**: Started separating `mobile.py` from the legacy Librera code to support multiple apps.

### Dec 23 (Monday) - Sync Expansion Planning
- Initiated work on expanding USB and Manual sync capabilities beyond Librera.
- Planned support for generic Android backup formats.

---

## Week 1: Foundation & Stabilization (Dec 18 - Dec 22, 2025)

### Dec 22 (Sunday) - Configuration & Polish
- **System Config**: Finalized paths for critical binaries (`ebook-convert`, `kepubify`).
- **UI Logic Fixes**: Corrected the visual behavior of "Prefer/Ignore" buttons for books/authors.

### Dec 19-21 (Thursday-Saturday) - Deployment & Debugging
- **Migration**: Successfully deployed the application to the Debian VM (Synology environment).
- **Critical Fixes**:
    - Resolved `flask_session` startup crashes.
    - Fixed "Grid View" rendering bugs for Series.
    - Restored missing admin sidebar links ("Access Requests").

### Dec 18 (Wednesday) - Inception
- **Project Setup**: Initial repository configuration.
- **Theme Modernization**: Updated the "CA Black" phpBB style to match the main application integration (CSS fixes, template events).
