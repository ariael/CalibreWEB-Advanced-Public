# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2018-2020 OzzieIsaacs
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

from flask import render_template, g, abort, request
from flask_babel import gettext as _
from werkzeug.local import LocalProxy
from .cw_login import current_user
from sqlalchemy.sql.expression import or_

from . import config, constants, logger, ub
from .ub import User
from .cache_manager import cache


log = logger.create()

def get_sidebar_config(kwargs=None):
    kwargs = kwargs or []
    simple = bool([e for e in ['kindle', 'tolino', "kobo", "bookeen"]
                   if (e in request.headers.get('User-Agent', "").lower())])
    if 'content' in kwargs:
        content = kwargs['content']
        content = isinstance(content, (User, LocalProxy)) and not content.role_anonymous()
    else:
        content = 'conf' in kwargs
    sidebar = list()
    sidebar.append({"glyph": "glyphicon-book", "text": _('Books'), "link": 'web.index', "id": "new",
                    "visibility": constants.SIDEBAR_RECENT, 'public': True, "page": "root",
                    "show_text": _('Show recent books'), "config_show":False})
    sidebar.append({"glyph": "glyphicon-fire", "text": _('Hot Books'), "link": 'web.books_list', "id": "hot",
                    "visibility": constants.SIDEBAR_HOT, 'public': True, "page": "hot",
                    "show_text": _('Show Hot Books'), "config_show": True})
    if current_user.role_admin():
        sidebar.append({"glyph": "glyphicon-download", "text": _('Downloaded Books'), "link": 'web.download_list',
                        "id": "download", "visibility": constants.SIDEBAR_DOWNLOAD, 'public': (not current_user.is_anonymous),
                        "page": "download", "show_text": _('Show Downloaded Books'),
                        "config_show": content})

    sidebar.append(
        {"glyph": "glyphicon-star", "text": _('Top Rated Books'), "link": 'web.books_list', "id": "rated",
         "visibility": constants.SIDEBAR_BEST_RATED, 'public': True, "page": "rated",
         "show_text": _('Show Top Rated Books'), "config_show": True})
    sidebar.append({"glyph": "glyphicon-eye-open", "text": _('Read Books'), "link": 'web.books_list', "id": "read",
                    "visibility": constants.SIDEBAR_READ_AND_UNREAD, 'public': (not current_user.is_anonymous),
                    "page": "read", "show_text": _('Show Read and Unread'), "config_show": content})
    sidebar.append(
        {"glyph": "glyphicon-eye-close", "text": _('Unread Books'), "link": 'web.books_list', "id": "unread",
         "visibility": constants.SIDEBAR_READ_AND_UNREAD, 'public': (not current_user.is_anonymous), "page": "unread",
         "show_text": _('Show unread'), "config_show": False})
    sidebar.append({"glyph": "glyphicon-random", "text": _('Discover'), "link": 'web.books_list', "id": "rand",
                    "visibility": constants.SIDEBAR_RANDOM, 'public': True, "page": "discover",
                    "show_text": _('Show Random Books'), "config_show": True})
    sidebar.append({"glyph": "glyphicon-inbox", "text": _('Categories'), "link": 'web.category_list', "id": "cat",
                    "visibility": constants.SIDEBAR_CATEGORY, 'public': True, "page": "category",
                    "show_text": _('Show Category Section'), "config_show": True})
    sidebar.append({"glyph": "glyphicon-bookmark", "text": _('Series'), "link": 'web.series_list', "id": "serie",
                    "visibility": constants.SIDEBAR_SERIES, 'public': True, "page": "series",
                    "show_text": _('Show Series Section'), "config_show": True})
    sidebar.append({"glyph": "glyphicon-check", "text": _('Series Tracker'), "link": 'web.series_tracker', "id": "serie_tracker",
                    "visibility": constants.SIDEBAR_SERIES_TRACKER, 'public': (not current_user.is_anonymous), "page": "series_tracker",
                    "show_text": _('Show Series Tracker'), "config_show": content})
    sidebar.append({"glyph": "glyphicon-user", "text": _('Authors'), "link": 'web.author_list', "id": "author",
                    "visibility": constants.SIDEBAR_AUTHOR, 'public': True, "page": "author",
                    "show_text": _('Show Author Section'), "config_show": True})
    sidebar.append({"glyph": "glyphicon-list-alt", "text": _('Author Management'), "link": 'web.author_dashboard', "id": "author_dashboard",
                    "visibility": constants.SIDEBAR_AUTHOR_DASHBOARD, 'public': (not current_user.is_anonymous), "page": "author_dashboard",
                    "show_text": _('Show Author Management'), "config_show": content})
    sidebar.append(
        {"glyph": "glyphicon-text-size", "text": _('Publishers'), "link": 'web.publisher_list', "id": "publisher",
         "visibility": constants.SIDEBAR_PUBLISHER, 'public': True, "page": "publisher",
         "show_text": _('Show Publisher Section'), "config_show":True})
    sidebar.append({"glyph": "glyphicon-flag", "text": _('Languages'), "link": 'web.language_overview', "id": "lang",
                    "visibility": constants.SIDEBAR_LANGUAGE, 'public': (current_user.filter_language() == 'all'),
                    "page": "language",
                    "show_text": _('Show Language Section'), "config_show": True})
    sidebar.append({"glyph": "glyphicon-star-empty", "text": _('Ratings'), "link": 'web.ratings_list', "id": "rate",
                    "visibility": constants.SIDEBAR_RATING, 'public': True,
                    "page": "rating", "show_text": _('Show Ratings Section'), "config_show": True})
    sidebar.append({"glyph": "glyphicon-file", "text": _('File formats'), "link": 'web.formats_list', "id": "format",
                    "visibility": constants.SIDEBAR_FORMAT, 'public': True,
                    "page": "format", "show_text": _('Show File Formats Section'), "config_show": True})
    sidebar.append(
        {"glyph": "glyphicon-folder-open", "text": _('Archived Books'), "link": 'web.books_list', "id": "archived",
         "visibility": constants.SIDEBAR_ARCHIVED, 'public': (not current_user.is_anonymous), "page": "archived",
         "show_text": _('Show Archived Books'), "config_show": content})
    sidebar.append(
        {"glyph": "glyphicon-ban-circle", "text": _('Ignored Items'), "link": 'web.ignored_list', "id": "ignored",
         "visibility": constants.SIDEBAR_CATEGORY, 'public': (not current_user.is_anonymous), "page": "ignored",
         "show_text": _('Show Ignored Items'), "config_show": content})
    sidebar.append(
        {"glyph": "glyphicon-heart", "text": _('Preferred Items'), "link": 'web.preferred_list', "id": "preferred",
         "visibility": constants.SIDEBAR_READ_AND_UNREAD, 'public': (not current_user.is_anonymous), "page": "preferred",
         "show_text": _('Show Preferred Items'), "config_show": content})
    
    # Access Requests for admins (phpBB workflow)
    if current_user.role_admin() or current_user.role_limited_admin():
        try:
            pending_count = ub.session.query(ub.AccessRequest).filter_by(status=0).count()
            badge_text = f" ({pending_count})" if pending_count > 0 else ""
            log.info(f"DEBUG: Adding Access Requests link (TOP). Admin={current_user.role_admin()}, Count={pending_count}")
            sidebar.insert(0, {"glyph": "glyphicon-inbox", "text": _("Access Requests") + badge_text, 
                            "link": 'admin.access_requests', "id": "access_req",
                            "visibility": constants.SIDEBAR_RECENT, 'public': True, "page": "access_requests",
                            "show_text": _("Show Access Requests"), "config_show": True})
        except Exception as e:
            log.error(f"Error adding Access Requests to sidebar: {e}")
    else:
        log.info(f"DEBUG: User {current_user.name} is not admin/limited_admin")
    
    
    if not simple:
        sidebar.append(
            {"glyph": "glyphicon-th-list", "text": _('Books List'), "link": 'web.books_table', "id": "list",
             "visibility": constants.SIDEBAR_LIST, 'public': (not current_user.is_anonymous), "page": "list",
             "show_text": _('Show Books List'), "config_show": content})
    g.shelves_access = ub.session.query(ub.Shelf).filter(
        or_(ub.Shelf.is_public == 1, ub.Shelf.user_id == current_user.id)).order_by(ub.Shelf.name).all()

    return sidebar, simple


# Returns the template for rendering and includes the instance name
def render_title_template(*args, **kwargs):
    sidebar, simple = get_sidebar_config(kwargs)
    
    # Global injection of book preferences for logged-in users
    if current_user.is_authenticated:
        try:
            # Books
            if 'pref_book_ids' not in kwargs:
                prefs = ub.session.query(ub.UserPreference).filter(
                    ub.UserPreference.user_id == current_user.id,
                    ub.UserPreference.item_type == constants.ITEM_TYPE_BOOK
                ).all()
                kwargs['pref_book_ids'] = {p.item_id: p.status for p in prefs}
            
            # Series
            if 'pref_series_ids' not in kwargs:
                prefs = ub.session.query(ub.UserPreference).filter(
                    ub.UserPreference.user_id == current_user.id,
                    ub.UserPreference.item_type == constants.ITEM_TYPE_SERIES
                ).all()
                kwargs['pref_series_ids'] = {p.item_id: p.status for p in prefs}

            # Authors
            if 'pref_author_ids' not in kwargs:
                prefs = ub.session.query(ub.UserPreference).filter(
                    ub.UserPreference.user_id == current_user.id,
                    ub.UserPreference.item_type == constants.ITEM_TYPE_AUTHOR
                ).all()
                kwargs['pref_author_ids'] = {p.item_id: p.status for p in prefs}
        except Exception as e:
            log.error(f"Error fetching user preferences: {e}")
            kwargs['pref_book_ids'] = {}
            kwargs['pref_series_ids'] = {}
            kwargs['pref_author_ids'] = {}

    try:
        return render_template(instance=config.config_calibre_web_title, sidebar=sidebar, simple=simple,
                               accept=config.config_upload_formats.split(','),
                               *args, **kwargs)
    except PermissionError:
        log.error("No permission to access {} file.".format(args[0]))
        abort(403)
