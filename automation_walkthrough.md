# Comprehensive Feature Documentation (Latest Updates)

This document outlines the major features and architectural improvements implemented in the last development cycle.

## 1. Author Intelligence & Bio Enrichment
A sophisticated system to bring your library to life by enriching author metadata.

- **Automated Bio Gathering**:
  - A background task (`TaskEnrichAuthors`) actively fetches author biographies, images, and birth/death dates from external sources (Wikipedia, Goodreads).
  - Data is stored in a dedicated `author_info` table for performance.
- **Author Dashboard**:
  - A new view accessible from the sidebar.
  - Displays rich profiles for authors, including their photo and biography.
  - Lists valid "Works" to help you identify missing books in your collection.
- **Smart Caching**:
  - Implements a 7-day refresh cycle with content hashing to minimize database writes and external API calls.

## 2. Multi-Library Watched Folders

We have implemented several high-impact features inspired by external projects like Calibre-Web-Automated and Hardcover.app. These additions focus on automation, manga support, and modern social integration.

## 1. Multi-Library Watched Folders
You can now automate the ingestion of books into specific libraries using **Watched Folders**.

- **How to use**:
  1. Go to **Admin** -> **Database Configuration**.
  2. Enable **Enable Automated Ingest (Watched Folders)**.
  3. In the **Manage Libraries** table, you will see a new **Watched Folder** column for each library.
  4. Specify a path for each library you want to automate (e.g., `/home/books/manga_ingest`).
  5. Save the configuration.
- **Workflow**:
  - Calibre-Web will periodically scan these folders.
  - New books found will be automatically added to the corresponding library.
  - Successfully processed files are moved to a `processed` subfolder within the watched directory.

## 2. Manga Metadata (AniList)
To support **Phase IV: Manga Excellence**, we added an AniList metadata provider.

- **Features**:
  - High-resolution covers from AniList.
  - Manga-specific tags and genres.
  - Staff extraction (Authors, Illustrators).
  - Integration with MyAnimeList (MAL) identifiers.
- **How to use**:
  - When editing a book or performing a bulk metadata search, AniList will now appear as an option.
  - It works best for Manga, Manhwa, and Light Novels.

## 3. Hardcover.app Integration
A modern social reading platform integration as requested.

- **How to use**:
  1. Register on [Hardcover.app](https://hardcover.app) and generate an API key in your account settings.
  2. Go to **Admin** -> **Edit Configuration**.
  3. Enter your **Hardcover API Key** in the Feature Configuration section.
  4. Hardcover will now be available as a metadata provider.
- **Benefits**:
  - Structured metadata via GraphQL.
  - Community ratings and social data.
  - Future potential for two-way progress syncing (scrobbling).

## 4. Multi-Library Switching
As a reminder from Phase I, you can switch between your libraries (e.g., Default, Manga, Sci-Fi) using the **Library Switcher** dropdown in the navigation bar. 

- This allows you to keep different content types separated while using the same Calibre-Web instance.
- Each library can now have its own ingest automation.

---

### Future Integration Opportunities:
- **Search & Request UI**: We can further simplify the "Book Downloader" experience by adding a "Request" button directly in the external search results.
- **Scrobbling**: Two-way sync with Hardcover and AniList for "Mark as Read" status.

## 5. Mobile Progress Sync & Cloud Integration
We have implemented a comprehensive solution for synchronizing reading progress between Android e-readers (Librera, Moon+ Reader, ReadEra) and Calibre-Web.

### Features
1.  **Automated Background Sync**:
    - Users can define a **Cloud Sync Path** in their profile (e.g., a mounted Google Drive folder).
    - Calibre-Web periodically scans this folder for app-specific progress files (`app-Progress.json`, `.mrpro`, `.bak`).
    - Reading progress is automatically extracted and applied to the database without user intervention.
2.  **Manual & USB Sync**:
    - Upload progress files manually via **Profile** -> **Mobile App Sync**.
    - **One-Click USB Sync**: If the server has ADB access to a connected device, it can pull progress files directly.
3.  **Smart Book Matching**:
    - The system now identifies books not just by exact title, but by:
      - **Calibre ID** in filenames (e.g., `Title (123).epub`).
      - **Title - Author** caching.
      - **UUID/ISBN** cross-referencing via improved OPDS feed metadata.

## 6. e-Reader Experience (OPDS Refinements)
The OPDS feed has been significantly optimized for a better "Store-like" experience on devices.

- **Kindle Optimization**:
  - Automatically offers **AZW3** format to Kindle devices.
  - If only EPUB exists, it performs **On-the-Fly Conversion** to AZW3/MOBI when downloading.
- **Format Filtering**:
  - Automatically hides irrelevant source files (DOCX, ORIGINAL_EPUB) from the feed.
  - Prioritizes the best format for the specific device connecting (Kobo gets KEPUB, Kindle gets AZW3).
- **Progress Sync (OPDS-PSE)**: 
  - Supports the OPDS-PSE standard, allowing compatible apps (Moon+ Reader, Librera) to sync progress purely via the network feed.
