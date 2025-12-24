# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify, abort
from .usermanagement import requires_basic_auth_if_no_ano, auth
from . import ub, calibre_db, logger, db

koreader = Blueprint('koreader', __name__)
log = logger.create()

@koreader.route("/koreader/sync/v1/progress/<path:document_id>", methods=["GET", "PUT"])
@requires_basic_auth_if_no_ano
def koreader_sync(document_id):
    user_id = int(auth.current_user().id)
    
    # Try to find book_id from document_id
    # document_id could be a UUID, filename, or MD5.
    # We'll try to match by UUID first, then filename.
    book = calibre_db.session.query(db.Books).filter(db.Books.uuid == document_id).first()
    if not book:
        # Try matching by filename (this is slow but might work for KOReader)
        # Often document_id is title.epub
        clean_id = document_id.replace('.epub', '').replace('.mobi', '').replace('.pdf', '')
        book = calibre_db.session.query(db.Books).filter(db.Books.title == clean_id).first()

    if not book:
        # Fallback: search for any book that might match
        log.debug(f"KOReader Sync: Document {document_id} not found by UUID or title")
        return jsonify({"status": "error", "message": "Book not found"}), 404

    read_book = ub.session.query(ub.ReadBook).filter(
        ub.ReadBook.user_id == user_id,
        ub.ReadBook.book_id == book.id
    ).first()

    if request.method == "GET":
        if not read_book:
            return jsonify({"percentage": 0.0, "progress": 0.0, "status": "unread"})
            
        return jsonify({
            "percentage": read_book.progress_percent,
            "progress": read_book.progress_percent / 100.0,
            "status": "finished" if read_book.read_status == 1 else "in_progress"
        })

    if request.method == "PUT":
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
            
        percentage = data.get("percentage")
        if percentage is None:
            # KOReader might send 'progress' as 0.0-1.0
            progress = data.get("progress")
            if progress is not None:
                percentage = progress * 100.0
        
        if percentage is None:
             return jsonify({"status": "error", "message": "No progress data"}), 400

        if not read_book:
            read_book = ub.ReadBook(user_id=user_id, book_id=book.id)
            ub.session.add(read_book)
            
        read_book.progress_percent = max(0.0, min(100.0, float(percentage)))
        if read_book.progress_percent >= 99.0:
            read_book.read_status = ub.ReadBook.STATUS_FINISHED
        elif read_book.progress_percent > 0.0:
            read_book.read_status = ub.ReadBook.STATUS_IN_PROGRESS
        else:
            read_book.read_status = ub.ReadBook.STATUS_UNREAD

        try:
            ub.session.commit()
            return jsonify({"status": "success"})
        except Exception as e:
            ub.session.rollback()
            log.error(f"KOReader Sync Failed: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
