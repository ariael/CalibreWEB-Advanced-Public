
# Add to cps/web.py

@web.route("/ajax/author/<int:author_id>/hierarchy")
@login_required_if_no_ano
def get_author_hierarchy(author_id):
    # Get Series for Author
    # Query: Select DISTINCT series from books where author_id = X
    # This is tricky in SQLAlchemy with N:M.
    # Actually, simpler: Get Author object, iterate books, collect series.
    try:
        author = calibre_db.session.query(db.Authors).filter(db.Authors.id == author_id).first()
        if not author:
            return jsonify({"success": False})
        
        series_map = {}
        standalone_books = []
        
        for book in author.books:
            if not common_filters_check(book): continue # helper to check permissions/visibility
            
            if book.series:
                for s in book.series:
                    if s.id not in series_map:
                        series_map[s.id] = {"id": s.id, "name": s.name, "count": 0, "books": []}
                    series_map[s.id]["count"] += 1
            else:
                standalone_books.append({
                    "id": book.id,
                    "title": book.title,
                    "has_cover": book.has_cover, # Helper needed? Web handles covers by ID.
                    "format": [f.format for f in book.data]
                })
        
        # Format series list
        series_list = []
        for sid, sdata in series_map.items():
            series_list.append(sdata)
        
        # Sort
        series_list.sort(key=lambda x: x["name"])
        standalone_books.sort(key=lambda x: x["title"])
        
        return jsonify({
            "success": True,
            "series": series_list,
            "books": standalone_books
        })
    except Exception as e:
        log.error(f"Hierarchy Error: {e}")
        return jsonify({"success": False})

@web.route("/ajax/series/<int:series_id>/books")
@login_required_if_no_ano
def get_series_books(series_id):
    try:
        series = calibre_db.session.query(db.Series).filter(db.Series.id == series_id).first()
        if not series:
             return jsonify({"success": False})
        
        books_list = []
        for book in series.books:
             if not common_filters_check(book): continue
             
             books_list.append({
                 "id": book.id,
                 "title": book.title,
                 "series_index": book.series_index,
                 "format": [f.format for f in book.data]
             })
             
        books_list.sort(key=lambda x: x["series_index"])
        return jsonify({"success": True, "books": books_list})
        
    except Exception as e:
        return jsonify({"success": False})

