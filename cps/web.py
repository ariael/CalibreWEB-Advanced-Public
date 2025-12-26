#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2018-2019 OzzieIsaacs, cervinko, jkrehm, bodybybuddha, ok11,
#                            andy29485, idalin, Kyosfonica, wuqi, Kennyl, lemmsh,
#                            falgh1, grunjol, csitko, ytils, xybydy, trasba, vrabe,
#                            ruben-herold, marblepebble, JackED42, SiphonSquirrel,
#                            apetresc, nanu-c, mutschler
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

import os
import json
import mimetypes
import chardet  # dependency of requests
import copy
from importlib.metadata import metadata

from flask import Blueprint, jsonify, request, redirect, send_from_directory, make_response, flash, abort, url_for
from flask import session as flask_session
from flask_babel import gettext as _
from flask_babel import get_locale
from .cw_login import login_user, logout_user, current_user
from flask_limiter import RateLimitExceeded
from flask_limiter.util import get_remote_address
from sqlalchemy.exc import IntegrityError, InvalidRequestError, OperationalError
from sqlalchemy.sql.expression import text, func, false, not_, and_, or_
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.functions import coalesce
from werkzeug.datastructures import Headers
from werkzeug.security import generate_password_hash, check_password_hash

from . import constants, logger, isoLanguages, services
from . import db, ub, config, app, audit_helper
from . import calibre_db, kobo_sync_status
from .search import render_search_results, render_adv_search_results
from .gdriveutils import getFileFromEbooksFolder, do_gdrive_download
from .helper import check_valid_domain, check_email, check_username, \
    get_book_cover, get_series_cover_thumbnail, get_download_link, send_mail, generate_random_password, \
    send_registration_mail, check_send_to_ereader, check_read_formats, tags_filters, reset_password, valid_email, \
    edit_book_read_status, valid_password, get_valid_filename
from .pagination import Pagination
from .redirect import get_redirect_location
from .cw_babel import get_available_locale
from .usermanagement import login_required_if_no_ano
from .kobo_sync_status import remove_synced_book
from .render_template import render_title_template
from .kobo_sync_status import change_archived_books
from . import limiter
from .services.worker import WorkerThread
from .tasks.bulk_download import TaskBulkDownload
from .tasks_status import render_task_status
from .usermanagement import user_login_required
from .string_helper import strip_whitespaces
import re
import time
from .phpbb_auth import phpBBAuth
from .approval import pending_user_check
from . import roles


feature_support = {
    'ldap': bool(services.ldap),
    'goodreads': bool(services.goodreads_support),
    'kobo': bool(services.kobo)
}

try:
    from .oauth_bb import oauth_check, register_user_with_oauth, logout_oauth_user, get_oauth_status

    feature_support['oauth'] = True
except ImportError:
    feature_support['oauth'] = False
    oauth_check = {}
    register_user_with_oauth = logout_oauth_user = get_oauth_status = None

from functools import wraps

try:
    from natsort import natsorted as sort
except ImportError:
    sort = sorted  # Just use regular sort then, may cause issues with badly named pages in cbz/cbr files


sql_version = metadata("sqlalchemy")["Version"]
sqlalchemy_version2 = ([int(x) if x.isnumeric() else 0 for x in sql_version.split('.')[:3]] >= [2, 0, 0])


@app.after_request
def add_security_headers(resp):
    default_src = ([host.strip() for host in config.config_trustedhosts.split(',') if host] +
                   ["'self'", "'unsafe-inline'", "'unsafe-eval'"])
    csp = "default-src " + ' '.join(default_src)
    if request.endpoint == "web.read_book" and config.config_use_google_drive:
        csp +=" blob: "
    csp += "; font-src 'self' data:"
    if request.endpoint == "web.read_book":
        csp += " blob: "
    csp += "; img-src 'self'"
    # Allow author photos from Wikipedia and Open Library
    if request.path.startswith("/author/"):
        csp += " upload.wikimedia.org covers.openlibrary.org"
        if config.config_use_goodreads:
            csp += " images.gr-assets.com i.gr-assets.com s.gr-assets.com"
    csp += " data:"
    if request.endpoint == "edit-book.show_edit_book" or config.config_use_google_drive:
        csp += " *"
    if request.endpoint == "web.read_book":
        csp += " blob: ; style-src-elem 'self' blob: 'unsafe-inline'"
    csp += "; object-src 'none';"
    resp.headers['Content-Security-Policy'] = csp
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    resp.headers['X-XSS-Protection'] = '1; mode=block'
    resp.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return resp


web = Blueprint('web', __name__)

log = logger.create()


# ################################### Login logic and rights management ###############################################


def download_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if current_user.role_download():
            return f(*args, **kwargs)
        abort(403)

    return inner


def viewer_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if current_user.role_viewer():
            return f(*args, **kwargs)
        abort(403)

    return inner


# ################################### phpBB Configuration Parser #######################################################

def load_phpbb_config():
    # Looking for /opt/calibre-web/phpbb_config.php or local one
    paths = ['/opt/calibre-web/phpbb_config.php', os.path.join(constants.BASE_DIR, 'phpbb_config.php')]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    content = f.read()
                config_data = {}
                # Extract $dbhost, $dbuser, $dbpasswd, $dbname, $table_prefix
                matches = re.findall(r'\$(\w+)\s*=\s*[\'"](.*?)[\'"];', content)
                for key, value in matches:
                    config_data[key] = value
                
                return {
                    'host': config_data.get('dbhost', 'localhost'),
                    'user': config_data.get('dbuser', ''),
                    'password': config_data.get('dbpasswd', ''),
                    'database': config_data.get('dbname', ''),
                    'prefix': config_data.get('table_prefix', 'phpbb_')
                }
            except Exception as e:
                log.error("Failed to parse phpBB config: %s", e)
    return None

# ################################### Waiting List Hook ###############################################################

@app.before_request
@pending_user_check
def check_pending():
    pass

# ################################### data provider functions #########################################################


@web.route("/switch_library/<int:lib_id>")
@user_login_required
def switch_library(lib_id):
    if lib_id == 0:
        flask_session.pop('current_library_path', None)
        flask_session.pop('current_library_name', None)
    else:
        try:
            lib = config.config_libraries[lib_id - 1]
            flask_session['current_library_path'] = lib['path']
            flask_session['current_library_name'] = lib['name']
        except (IndexError, TypeError):
            flash(_("Library not found"), category="error")

    # Clear cache
    calibre_db.clear_cache()
    return redirect(url_for('web.index'))


@web.route("/ajax/emailstat")
@user_login_required
def get_email_status_json():
    tasks = WorkerThread.get_instance().tasks
    return jsonify(render_task_status(tasks))


@web.route("/ajax/bookmark/<int:book_id>/<book_format>", methods=['POST'])
@user_login_required
def set_bookmark(book_id, book_format):
    bookmark_key = request.form["bookmark"]
    ub.session.query(ub.Bookmark).filter(and_(ub.Bookmark.user_id == int(current_user.id),
                                              ub.Bookmark.book_id == book_id,
                                              ub.Bookmark.format == book_format)).delete()
    if not bookmark_key:
        ub.session_commit()
        return "", 204

    l_bookmark = ub.Bookmark(user_id=current_user.id,
                             book_id=book_id,
                             format=book_format,
                             bookmark_key=bookmark_key)
    ub.session.merge(l_bookmark)
    ub.session_commit("Bookmark for user {} in book {} created".format(current_user.id, book_id))
    return "", 201


@web.route("/ajax/toggleread/<int:book_id>", methods=['POST'])
@user_login_required
def toggle_read(book_id):
    message = edit_book_read_status(book_id)
    if message:
        return message, 400
    else:
        return message


@web.route("/ajax/togglearchived/<int:book_id>", methods=['POST'])
@user_login_required
def toggle_archived(book_id):
    change_archived_books(book_id, message="Book {} archive bit toggled".format(book_id))
    # Remove book from syncd books list to force resync (?)
    remove_synced_book(book_id)
    return ""


@web.route("/ajax/toggle_preference/<int:item_type>/<int:item_id>", methods=['POST'])
@login_required_if_no_ano
def toggle_preference(item_type, item_id):
    status = request.form.get('status')
    if status is None:
        return "Missing status", 400
    try:
        status = int(status)
    except ValueError:
        return "Invalid status", 400

    if item_type not in [constants.ITEM_TYPE_BOOK, constants.ITEM_TYPE_SERIES, constants.ITEM_TYPE_AUTHOR]:
        return "Invalid item type", 400

    # Check if preference exists
    pref = ub.session.query(ub.UserPreference).filter(
        ub.UserPreference.user_id == current_user.id,
        ub.UserPreference.item_type == item_type,
        ub.UserPreference.item_id == item_id
    ).first()

    if status == 0:
        # Remove preference
        if pref:
            ub.session.delete(pref)
            ub.session_commit()
        return "", 204
    
    if not pref:
        pref = ub.UserPreference(
            user_id=current_user.id,
            item_type=item_type,
            item_id=item_id,
            status=status
        )
        ub.session.add(pref)
    else:
        pref.status = status
        # pref.last_modified will update automatically due to onupdate
    
    ub.session_commit()
    return "", 200


@web.route("/ajax/view", methods=["POST"])
@login_required_if_no_ano
def update_view():
    to_save = request.get_json()
    try:
        for element in to_save:
            for param in to_save[element]:
                current_user.set_view_property(element, param, to_save[element][param])
    except Exception as ex:
        log.error("Could not save view_settings: %r %r: %e", request, to_save, ex)
        return "Invalid request", 400
    return "1", 200


'''
@web.route("/ajax/getcomic/<int:book_id>/<book_format>/<int:page>")
@user_login_required
def get_comic_book(book_id, book_format, page):
    book = calibre_db.get_book(book_id)
    if not book:
        return "", 204
    else:
        for bookformat in book.data:
            if bookformat.format.lower() == book_format.lower():
                cbr_file = os.path.join(config.config_calibre_dir, book.path, bookformat.name) + "." + book_format
                if book_format in ("cbr", "rar"):
                    if feature_support['rar'] == True:
                        rarfile.UNRAR_TOOL = config.config_rarfile_location
                        try:
                            rf = rarfile.RarFile(cbr_file)
                            names = sort(rf.namelist())
                            extract = lambda page: rf.read(names[page])
                        except:
                            # rarfile not valid
                            log.error('Unrar binary not found, or unable to decompress file %s', cbr_file)
                            return "", 204
                    else:
                        log.info('Unrar is not supported please install python rarfile extension')
                        # no support means return nothing
                        return "", 204
                elif book_format in ("cbz", "zip"):
                    zf = zipfile.ZipFile(cbr_file)
                    names=sort(zf.namelist())
                    extract = lambda page: zf.read(names[page])
                elif book_format in ("cbt", "tar"):
                    tf = tarfile.TarFile(cbr_file)
                    names=sort(tf.getnames())
                    extract = lambda page: tf.extractfile(names[page]).read()
                else:
                    log.error('unsupported comic format')
                    return "", 204

                b64 = codecs.encode(extract(page), 'base64').decode()
                ext = names[page].rpartition('.')[-1]
                if ext not in ('png', 'gif', 'jpg', 'jpeg', 'webp'):
                    ext = 'png'
                extractedfile="data:image/" + ext + ";base64," + b64
                fileData={"name": names[page], "page":page, "last":len(names)-1, "content": extractedfile}
                return make_response(json.dumps(fileData))
        return "", 204
'''


# ################################### Typeahead ##################################################################


@web.route("/get_authors_json", methods=['GET'])
@login_required_if_no_ano
def get_authors_json():
    return calibre_db.get_typeahead(db.Authors, request.args.get('q'), ('|', ','))


@web.route("/get_publishers_json", methods=['GET'])
@login_required_if_no_ano
def get_publishers_json():
    return calibre_db.get_typeahead(db.Publishers, request.args.get('q'), ('|', ','))


@web.route("/get_tags_json", methods=['GET'])
@login_required_if_no_ano
def get_tags_json():
    return calibre_db.get_typeahead(db.Tags, request.args.get('q'), tag_filter=tags_filters())


@web.route("/get_series_json", methods=['GET'])
@login_required_if_no_ano
def get_series_json():
    return calibre_db.get_typeahead(db.Series, request.args.get('q'))


@web.route("/get_languages_json", methods=['GET'])
@login_required_if_no_ano
def get_languages_json():
    query = (request.args.get('q') or '').lower()
    language_names = isoLanguages.get_language_names(get_locale())
    entries_start = [s for key, s in language_names.items() if s.lower().startswith(query.lower())]
    if len(entries_start) < 5:
        entries = [s for key, s in language_names.items() if query in s.lower()]
        entries_start.extend(entries[0:(5 - len(entries_start))])
        entries_start = list(set(entries_start))
    json_dumps = json.dumps([dict(name=r) for r in entries_start[0:5]])
    return json_dumps


@web.route("/get_matching_tags", methods=['GET'])
@login_required_if_no_ano
def get_matching_tags():
    tag_dict = {'tags': []}
    q = calibre_db.session.query(db.Books).filter(calibre_db.common_filters(True))
    calibre_db.create_functions()
    # calibre_db.session.connection().connection.connection.create_function("lower", 1, db.lcase)
    author_input = request.args.get('authors') or ''
    title_input = request.args.get('title') or ''
    include_tag_inputs = request.args.getlist('include_tag') or ''
    exclude_tag_inputs = request.args.getlist('exclude_tag') or ''
    q = q.filter(db.Books.authors.any(func.lower(db.Authors.name).ilike("%" + author_input + "%")),
                 func.lower(db.Books.title).ilike("%" + title_input + "%"))
    if len(include_tag_inputs) > 0:
        for tag in include_tag_inputs:
            q = q.filter(db.Books.tags.any(db.Tags.id == tag))
    if len(exclude_tag_inputs) > 0:
        for tag in exclude_tag_inputs:
            q = q.filter(not_(db.Books.tags.any(db.Tags.id == tag)))
    for book in q:
        for tag in book.tags:
            if tag.id not in tag_dict['tags']:
                tag_dict['tags'].append(tag.id)
    json_dumps = json.dumps(tag_dict)
    return json_dumps


def generate_char_list(entries): # data_colum, db_link):
    char_list = list()
    for entry in entries:
        upper_char = entry[0].name[0].upper()
        if upper_char not in char_list:
            char_list.append(upper_char)
    return char_list


def query_char_list(data_colum, db_link):
    results = (calibre_db.session.query(func.upper(func.substr(data_colum, 1, 1)).label('char'))
            .join(db_link).join(db.Books).filter(calibre_db.common_filters())
            .group_by(func.upper(func.substr(data_colum, 1, 1))).all())
    return results


def get_sort_function(sort_param, data):
    order = [db.Books.timestamp.desc()]
    if sort_param == 'stored':
        sort_param = current_user.get_view_property(data, 'stored')
    else:
        current_user.set_view_property(data, 'stored', sort_param)
    if sort_param == 'pubnew':
        order = [db.Books.pubdate.desc()]
    if sort_param == 'pubold':
        order = [db.Books.pubdate]
    if sort_param == 'abc':
        order = [db.Books.sort]
    if sort_param == 'zyx':
        order = [db.Books.sort.desc()]
    if sort_param == 'new':
        order = [db.Books.timestamp.desc()]
    if sort_param == 'old':
        order = [db.Books.timestamp]
    if sort_param == 'authaz':
        order = [db.Books.author_sort.asc(), db.Series.name, db.Books.series_index]
    if sort_param == 'authza':
        order = [db.Books.author_sort.desc(), db.Series.name.desc(), db.Books.series_index.desc()]
    if sort_param == 'seriesasc':
        order = [db.Books.series_index.asc()]
    if sort_param == 'seriesdesc':
        order = [db.Books.series_index.desc()]
    if sort_param == 'hotdesc':
        order = [func.count(ub.Downloads.book_id).desc()]
    if sort_param == 'hotasc':
        order = [func.count(ub.Downloads.book_id).asc()]
    if sort_param is None:
        sort_param = "new"
    return order, sort_param


def render_books_list(data, sort_param, book_id, page):
    order = get_sort_function(sort_param, data)
    view_type = current_user.get_view_property(data or 'newest', 'view_type')
    template = 'index.html'
    if view_type == 'table':
        template = 'list.html'

    if data == "rated":
        return render_rated_books(page, book_id, order=order)
    elif data == "discover":
        return render_discover_books(book_id)
    elif data == "unread":
        return render_read_books(page, False, order=order)
    elif data == "read":
        return render_read_books(page, True, order=order)
    elif data == "hot":
        return render_hot_books(page, order)
    elif data == "download":
        return render_downloaded_books(page, order, book_id)
    elif data == "author":
        return render_author_books(page, book_id, order)
    elif data == "publisher":
        return render_publisher_books(page, book_id, order)
    elif data == "series":
        return render_series_books(page, book_id, order)
    elif data == "ratings":
        return render_ratings_books(page, book_id, order)
    elif data == "formats":
        return render_formats_books(page, book_id, order)
    elif data == "category":
        return render_category_books(page, book_id, order)
    elif data == "language":
        return render_language_books(page, book_id, order)
    elif data == "archived":
        return render_archived_books(page, order)
    elif data == "search":
        term = request.args.get('query', None)
        offset = int(int(config.config_books_per_page) * (page - 1))
        return render_search_results(term, offset, order, config.config_books_per_page)
    elif data == "advsearch":
        term = json.loads(flask_session.get('query', '{}'))
        offset = int(int(config.config_books_per_page) * (page - 1))
        return render_adv_search_results(term, offset, order, config.config_books_per_page)
    else:
        website = data or "newest"
        entries, random, pagination = calibre_db.fill_indexpage(page, 0, db.Books, True, order[0],
                                                                True, config.config_read_column,
                                                                db.books_series_link,
                                                                db.Books.id == db.books_series_link.c.book,
                                                                db.Series)
        return render_title_template(template, random=random, entries=entries, pagination=pagination,
                                     title=_("Books"), page=website, data=website, order=order[1])


def render_rated_books(page, book_id, order):
    if current_user.check_visibility(constants.SIDEBAR_BEST_RATED):
        view_type = current_user.get_view_property('rated', 'view_type')
        template = 'index.html' if view_type != 'table' else 'list.html'
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db.Books.ratings.any(db.Ratings.rating > 9),
                                                                order[0],
                                                                True, config.config_read_column,
                                                                db.books_series_link,
                                                                db.Books.id == db.books_series_link.c.book,
                                                                db.Series)

        return render_title_template(template, random=random, entries=entries, pagination=pagination,
                                     id=book_id, title=_("Top Rated Books"), page="rated", data="rated", order=order[1])
    else:
        abort(404)


def render_discover_books(book_id):
    if current_user.check_visibility(constants.SIDEBAR_RANDOM):
        view_type = current_user.get_view_property('discover', 'view_type')
        template = 'index.html' if view_type != 'table' else 'list.html'
        entries, __, ___ = calibre_db.fill_indexpage(1, 0, db.Books, True, [func.randomblob(2)],
                                                            join_archive_read=True,
                                                            config_read_column=config.config_read_column)
        pagination = Pagination(1, config.config_books_per_page, config.config_books_per_page)
        return render_title_template(template, random=false(), entries=entries, pagination=pagination, id=book_id,
                                     title=_("Discover (Random Books)"), page="discover", data="discover")
    else:
        abort(404)


def render_hot_books(page, order):
    if current_user.check_visibility(constants.SIDEBAR_HOT):
        if order[1] not in ['hotasc', 'hotdesc']:
            # Unary expression comparison only working (for this expression) in sqlalchemy 1.4+
            # if not (order[0][0].compare(func.count(ub.Downloads.book_id).desc()) or
            #        order[0][0].compare(func.count(ub.Downloads.book_id).asc())):
            order = [func.count(ub.Downloads.book_id).desc()], 'hotdesc'
        if current_user.show_detail_random():
            random_query = calibre_db.generate_linked_query(config.config_read_column, db.Books)
            random = (random_query.filter(calibre_db.common_filters())
                     .order_by(func.random())
                     .limit(config.config_random_books).all())
        else:
            random = false()

        off = int(int(config.config_books_per_page) * (page - 1))
        all_books = ub.session.query(ub.Downloads, func.count(ub.Downloads.book_id)) \
            .order_by(*order[0]).group_by(ub.Downloads.book_id)
        hot_books = all_books.offset(off).limit(config.config_books_per_page)
        entries = list()
        for book in hot_books:
            query = calibre_db.generate_linked_query(config.config_read_column, db.Books)
            download_book = query.filter(calibre_db.common_filters()).filter(
                book.Downloads.book_id == db.Books.id).first()
            if download_book:
                entries.append(download_book)
            else:
                ub.delete_download(book.Downloads.book_id)
        num_books = entries.__len__()
        pagination = Pagination(page, config.config_books_per_page, num_books)
        view_type = current_user.get_view_property('hot', 'view_type')
        template = 'index.html' if view_type != 'table' else 'list.html'
        return render_title_template(template, random=random, entries=entries, pagination=pagination,
                                     title=_("Hot Books (Most Downloaded)"), page="hot", data="hot", order=order[1])
    else:
        abort(404)


def render_downloaded_books(page, order, user_id):
    if current_user.role_admin():
        user_id = int(user_id)
    else:
        user_id = current_user.id
    user = ub.session.query(ub.User).filter(ub.User.id == user_id).first()
    if current_user.check_visibility(constants.SIDEBAR_DOWNLOAD) and user:
        entries, random, pagination = calibre_db.fill_indexpage(page,
                                                            0,
                                                            db.Books,
                                                            ub.Downloads.user_id == user_id,
                                                            order[0],
                                                            True, config.config_read_column,
                                                            db.books_series_link,
                                                            db.Books.id == db.books_series_link.c.book,
                                                            db.Series,
                                                            ub.Downloads, db.Books.id == ub.Downloads.book_id)
        for book in entries:
            if not (calibre_db.session.query(db.Books).filter(calibre_db.common_filters())
                    .filter(db.Books.id == book.Books.id).first()):
                ub.delete_download(book.Books.id)
        return render_title_template('index.html',
                                     random=random,
                                     entries=entries,
                                     pagination=pagination,
                                     id=user_id,
                                     title=_("Downloaded books by %(user)s", user=user.name),
                                     page="download",
                                     order=order[1])
    else:
        abort(404)


def render_author_books(page, author_id, order):
    entries, __, pagination = calibre_db.fill_indexpage(page, 0,
                                                        db.Books,
                                                        db.Books.authors.any(db.Authors.id == author_id),
                                                        [order[0][0], db.Series.name, db.Books.series_index],
                                                        True, config.config_read_column,
                                                        db.books_series_link,
                                                        db.books_series_link.c.book == db.Books.id,
                                                        db.Series)
    if entries is None:
        entries = []
    
    if sqlalchemy_version2:
        author = calibre_db.session.get(db.Authors, author_id)
    else:
        author = calibre_db.session.query(db.Authors).get(author_id)
        
    if not author:
        flash(_("Author not found"), category="error")
        return redirect(url_for("web.index"))

    author_name = author.name.replace('|', ',')
    other_books = []
    
    # DIRECT DATABASE QUERY - get cached author info if it exists
    author_info = ub.session.query(ub.AuthorInfo).filter(ub.AuthorInfo.author_id == author_id).first()
    
    # Log what we found for debugging
    if author_info:
        log.debug("Found author_info for %s: bio=%s, image=%s", 
                 author_name, 
                 bool(author_info.biography), 
                 bool(author_info.image_url))
    else:
        log.debug("No author_info found for %s (id=%d)", author_name, author_id)
    
    # Try Goodreads if no cached data and Goodreads is enabled
    if not author_info and services.goodreads_support and config.config_use_goodreads:
        author_info = services.goodreads_support.get_author_info(author_name)
        if author_info:
            book_entries = [entry.Books for entry in entries]
            other_books = services.goodreads_support.get_other_books(author_info, book_entries)
    
    # Final fallback - use basic author object from Calibre DB
    if not author_info:
        # Create a simple object with required attributes
        class AuthorDisplay:
            pass
        author_info = AuthorDisplay()
        author_info.author_name = author_name
        author_info.name = author.name
        author_info.biography = None
        author_info.image_url = None
        author_info.link = None

    # Ensure author_name is set for template
    if not hasattr(author_info, 'author_name'):
        author_info.author_name = author_name

    # Calculate missing books from bibliography
    missing_books = services.author_enrichment.get_missing_books(author_id)
    log.debug("Found %d missing books for author %d", len(missing_books), author_id)

    return render_title_template('author.html', entries=entries, pagination=pagination, id=author_id,
                                 title=_("Author: %(name)s", name=author_name), author=author_info,
                                 other_books=other_books, missing_books=missing_books,
                                 page="author", order=order[1])


@web.route("/author/refresh/<int:author_id>", methods=["POST"])
@login_required_if_no_ano
def refresh_author_info(author_id):
    """
    AJAX endpoint to refresh a single author's info from Open Library.
    Forces a fresh fetch even if data was recently checked.
    """
    from flask import jsonify
    
    if sqlalchemy_version2:
        author = calibre_db.session.get(db.Authors, author_id)
    else:
        author = calibre_db.session.query(db.Authors).get(author_id)
    
    if not author:
        return jsonify({"success": False, "error": _("Author not found")})
    
    author_name = author.name.replace('|', ',')
    
    try:
        # Force refresh from Open Library
        from cps.services.author_enrichment import fetch_author_info
        new_data = fetch_author_info(author_name)
        
        if new_data:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            # Get or create author_info record
            author_info = ub.session.query(ub.AuthorInfo).filter(
                ub.AuthorInfo.author_id == author_id).first()
            
            if not author_info:
                author_info = ub.AuthorInfo(
                    author_id=author_id,
                    author_name=author_name,
                    biography=new_data.get("biography"),
                    image_url=new_data.get("image_url"),
                    content_hash=new_data.get("content_hash"),
                    last_updated=now,
                    last_checked=now
                )
                ub.session.add(author_info)
            else:
                author_info.biography = new_data.get("biography")
                author_info.image_url = new_data.get("image_url")
                author_info.content_hash = new_data.get("content_hash")
                author_info.last_updated = now
                author_info.last_checked = now
            
            ub.session.commit()
            
            return jsonify({
                "success": True,
                "message": _("Author info updated successfully"),
                "biography": new_data.get("biography", "")[:200] + "..." if new_data.get("biography") else None,
                "image_url": new_data.get("image_url"),
                "work_count": new_data.get("work_count", 0)
            })
        else:
            return jsonify({
                "success": False,
                "error": _("No data found for this author on Open Library")
            })
            
    except Exception as e:
        log.error("Error refreshing author %s: %s", author_name, str(e))
        return jsonify({"success": False, "error": str(e)})


def render_publisher_books(page, book_id, order):
    if book_id == '-1':
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db.Publishers.name == None,
                                                                [db.Series.name, order[0][0], db.Books.series_index],
                                                                True, config.config_read_column,
                                                                db.books_publishers_link,
                                                                db.Books.id == db.books_publishers_link.c.book,
                                                                db.Publishers,
                                                                db.books_series_link,
                                                                db.Books.id == db.books_series_link.c.book,
                                                                db.Series)
        publisher = _("None")
    else:
        publisher = calibre_db.session.query(db.Publishers).filter(db.Publishers.id == book_id).first()
        if publisher:
            entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                    db.Books,
                                                                    db.Books.publishers.any(
                                                                        db.Publishers.id == book_id),
                                                                    [db.Series.name, order[0][0],
                                                                     db.Books.series_index],
                                                                    True, config.config_read_column,
                                                                    db.books_series_link,
                                                                    db.Books.id == db.books_series_link.c.book,
                                                                    db.Series)
            publisher = publisher.name
        else:
            abort(404)

    return render_title_template('index.html', random=random, entries=entries, pagination=pagination, id=book_id,
                                 title=_("Publisher: %(name)s", name=publisher),
                                 page="publisher",
                                 order=order[1])


def render_series_books(page, book_id, order):
    if book_id == '-1':
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db.Series.name == None,
                                                                [order[0][0]],
                                                                True, config.config_read_column,
                                                                db.books_series_link,
                                                                db.Books.id == db.books_series_link.c.book,
                                                                db.Series)
        series_name = _("None")
    else:
        series_obj = calibre_db.session.query(db.Series).filter(db.Series.id == book_id).first()
        if series_obj:
            entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                    db.Books,
                                                                    db.Books.series.any(db.Series.id == book_id),
                                                                    [order[0][0]],
                                                                    True, config.config_read_column)
            series_name = series_obj.name
        else:
            abort(404)
            
    # Find missing series books - Only for ADMINS and using CACHED data to avoid load
    missing_series_books = []
    if current_user.role_admin() and book_id != '-1' and series_name:
        try:
            from .services import author_enrichment
            authors_ids = set()
            for entry in entries:
                book = entry.Books if hasattr(entry, 'Books') else (entry[0] if isinstance(entry, (list, tuple)) else entry)
                for author in book.authors:
                    authors_ids.add(author.id)
            
            # Get cached bibliographies for all authors of this series
            author_infos = ub.session.query(ub.AuthorInfo).filter(ub.AuthorInfo.author_id.in_(list(authors_ids))).all()
            
            # Aggregate all potential works from cache
            all_cached_works = []
            for info in author_infos:
                if info.works:
                    all_cached_works.extend(info.works)
            
            if all_cached_works:
                # Filter works by checking if they contain/match the series name
                norm_series = author_enrichment.normalize_book_title(series_name)
                owned_normalized = {author_enrichment.normalize_book_title(e.Books.title if hasattr(e, 'Books') else e.title) for e in entries}
                
                for work_title in set(all_cached_works):
                    norm_work = author_enrichment.normalize_book_title(work_title)
                    # If work title contains series name and we don't own it
                    if norm_series in norm_work and norm_work not in owned_normalized:
                        # Double check fuzzy Match
                        is_owned = False
                        for ot in owned_normalized:
                            if ot and (ot in norm_work or norm_work in ot):
                                is_owned = True
                                break
                        if not is_owned:
                            missing_series_books.append(work_title)

        except Exception as e:
            logger.create().error("Failed to lookup cached missing series books for %s: %s", series_name, e)

    return render_title_template('index.html', random=random, pagination=pagination, entries=entries, id=book_id,
                                 title=_("Series: %(serie)s", serie=series_name), page="series", order=order[1],
                                 missing_series_books=sorted(list(set(missing_series_books))))


def render_ratings_books(page, book_id, order):
    if book_id == '-1':
        db_filter = coalesce(db.Ratings.rating, 0) < 1
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db_filter,
                                                                [order[0][0]],
                                                                True, config.config_read_column,
                                                                db.books_ratings_link,
                                                                db.Books.id == db.books_ratings_link.c.book,
                                                                db.Ratings)
        title = _("Rating: None")
    else:
        name = calibre_db.session.query(db.Ratings).filter(db.Ratings.id == book_id).first()
        if name:
            entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                    db.Books,
                                                                    db.Books.ratings.any(db.Ratings.id == book_id),
                                                                    [order[0][0]],
                                                                    True, config.config_read_column)
            title = _("Rating: %(rating)s stars", rating=int(name.rating / 2))
        else:
            abort(404)
    return render_title_template('index.html', random=random, pagination=pagination, entries=entries, id=book_id,
                                 title=title, page="ratings", order=order[1])


def render_formats_books(page, book_id, order):
    if book_id == '-1':
        name = _("None")
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db.Data.format == None,
                                                                [order[0][0]],
                                                                True, config.config_read_column,
                                                                db.Data)

    else:
        name = calibre_db.session.query(db.Data).filter(db.Data.format == book_id.upper()).first()
        if name:
            name = name.format
            entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                    db.Books,
                                                                    db.Books.data.any(
                                                                        db.Data.format == book_id.upper()),
                                                                    [order[0][0]],
                                                                    True, config.config_read_column)
        else:
            abort(404)

    return render_title_template('index.html', random=random, pagination=pagination, entries=entries, id=book_id,
                                 title=_("File format: %(format)s", format=name),
                                 page="formats",
                                 order=order[1])


def render_category_books(page, book_id, order):
    if book_id == '-1':
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db.Tags.name == None,
                                                                [order[0][0], db.Series.name, db.Books.series_index],
                                                                True, config.config_read_column,
                                                                db.books_tags_link,
                                                                db.Books.id == db.books_tags_link.c.book,
                                                                db.Tags,
                                                                db.books_series_link,
                                                                db.Books.id == db.books_series_link.c.book,
                                                                db.Series)
        tagsname = _("None")
    else:
        tagsname = calibre_db.session.query(db.Tags).filter(db.Tags.id == book_id).first()
        if tagsname:
            entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                    db.Books,
                                                                    db.Books.tags.any(db.Tags.id == book_id),
                                                                    [order[0][0], db.Series.name,
                                                                     db.Books.series_index],
                                                                    True, config.config_read_column,
                                                                    db.books_series_link,
                                                                    db.Books.id == db.books_series_link.c.book,
                                                                    db.Series)
            tagsname = tagsname.name
        else:
            abort(404)
    return render_title_template('index.html', random=random, entries=entries, pagination=pagination, id=book_id,
                                 title=_("Category: %(name)s", name=tagsname), page="category", order=order[1])


def render_language_books(page, name, order):
    try:
        if name.lower() != "none":
            lang_name = isoLanguages.get_language_name(get_locale(), name)
            if lang_name == "Unknown":
                abort(404)
        else:
            lang_name = _("None")
    except KeyError:
        abort(404)
    if name == "none":
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db.Languages.lang_code == None,
                                                                [order[0][0]],
                                                                True, config.config_read_column,
                                                                db.books_languages_link,
                                                                db.Books.id == db.books_languages_link.c.book,
                                                                db.Languages)
    else:
        entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                                db.Books,
                                                                db.Books.languages.any(db.Languages.lang_code == name),
                                                                [order[0][0]],
                                                                True, config.config_read_column)
    return render_title_template('index.html', random=random, entries=entries, pagination=pagination, id=name,
                                 title=_("Language: %(name)s", name=lang_name), page="language", order=order[1])


def render_read_books(page, are_read, as_xml=False, order=None):
    sort_param = order[0] if order else []
    if not config.config_read_column:
        if are_read:
            db_filter = and_(ub.ReadBook.user_id == int(current_user.id),
                             ub.ReadBook.read_status == ub.ReadBook.STATUS_FINISHED)
        else:
            db_filter = coalesce(ub.ReadBook.read_status, 0) != ub.ReadBook.STATUS_FINISHED
    else:
        try:
            if are_read:
                db_filter = db.cc_classes[config.config_read_column].value == True
            else:
                db_filter = coalesce(db.cc_classes[config.config_read_column].value, False) != True
        except (KeyError, AttributeError, IndexError):
            log.error("Custom Column No.{} does not exist in calibre database".format(config.config_read_column))
            if not as_xml:
                flash(_("Custom Column No.%(column)d does not exist in calibre database",
                        column=config.config_read_column),
                      category="error")
                return redirect(url_for("web.index"))
            return []  # ToDo: Handle error Case for opds

    entries, random, pagination = calibre_db.fill_indexpage(page, 0,
                                                            db.Books,
                                                            db_filter,
                                                            sort_param,
                                                            True, config.config_read_column,
                                                            db.books_series_link,
                                                            db.Books.id == db.books_series_link.c.book,
                                                            db.Series)

    if as_xml:
        return entries, pagination
    else:
        if are_read:
            name = _('Read Books') + ' (' + str(pagination.total_count) + ')'
            page_name = "read"
        else:
            name = _('Unread Books') + ' (' + str(pagination.total_count) + ')'
            page_name = "unread"
        view_type = current_user.get_view_property(page_name, 'view_type')
        template = 'index.html' if view_type != 'table' else 'list.html'
        return render_title_template(template, random=random, entries=entries, pagination=pagination,
                                     title=name, page=page_name, data=page_name, order=order[1] if order else None)


def render_archived_books(page, sort_param):
    order = sort_param[0] or []
    archived_books = (ub.session.query(ub.ArchivedBook)
                      .filter(ub.ArchivedBook.user_id == int(current_user.id))
                      .filter(ub.ArchivedBook.is_archived == True)
                      .all())
    archived_book_ids = [archived_book.book_id for archived_book in archived_books]

    archived_filter = db.Books.id.in_(archived_book_ids)

    entries, random, pagination = calibre_db.fill_indexpage_with_archived_books(page, db.Books,
                                                                                0,
                                                                                archived_filter,
                                                                                order,
                                                                                True,
                                                                                True, config.config_read_column)

    name = _('Archived Books') + ' (' + str(len(entries)) + ')'
    page_name = "archived"
    return render_title_template('index.html', random=random, entries=entries, pagination=pagination,
                                 title=name, page=page_name, order=sort_param[1])


# ################################### View Books list ##################################################################


@web.route("/", defaults={'page': 1})
@web.route("/")
@web.route("/<int:page>")
@login_required_if_no_ano
def index(page=1):
    if current_user.check_visibility(constants.SIDEBAR_SERIES):
        return series_list()
    return render_books_list("newest", "stored", 0, page)


@login_required_if_no_ano
def books_list(data, sort_param, book_id, page):
    return render_books_list(data, sort_param, book_id, page)

# Limit number of routes to avoid redirects
data =["rated", "discover", "unread", "read", "hot", "download", "author", "publisher", "series", "ratings", "formats",
       "category", "language", "archived", "search", "advsearch", "newest"]
for d in data:
    web.add_url_rule('/{}/<sort_param>'.format(d), view_func=books_list, defaults={'page': 1, 'book_id': 1, "data": d})
    web.add_url_rule('/{}/<sort_param>/'.format(d), view_func=books_list, defaults={'page': 1, 'book_id': 1, "data": d})
    web.add_url_rule('/{}/<sort_param>/<book_id>'.format(d), view_func=books_list, defaults={'page': 1, "data": d})
    web.add_url_rule('/{}/<sort_param>/<book_id>/<int:page>'.format(d), defaults={"data": d}, view_func=books_list)


@web.route("/table")
@user_login_required
def books_table():
    visibility = current_user.view_settings.get('table', {})
    cc = calibre_db.get_cc_columns(config, filter_config_custom_read=True)
    return render_title_template('book_table.html', title=_("Books List"), cc=cc, page="book_table",
                                 visiblility=visibility)


@web.route("/ajax/listbooks")
@user_login_required
def list_books():
    off = int(request.args.get("offset") or 0)
    limit = int(request.args.get("limit") or config.config_books_per_page)
    search_param = request.args.get("search")
    sort_param = request.args.get("sort", "id")
    order = request.args.get("order", "").lower()
    state = None
    join = tuple()

    if sort_param == "state":
        state = json.loads(request.args.get("state", "[]"))
    elif sort_param == "tags":
        order = [db.Tags.name.asc()] if order == "asc" else [db.Tags.name.desc()]
        join = db.books_tags_link, db.Books.id == db.books_tags_link.c.book, db.Tags
    elif sort_param == "series":
        order = [db.Series.name.asc()] if order == "asc" else [db.Series.name.desc()]
        join = db.books_series_link, db.Books.id == db.books_series_link.c.book, db.Series
    elif sort_param == "publishers":
        order = [db.Publishers.name.asc()] if order == "asc" else [db.Publishers.name.desc()]
        join = db.books_publishers_link, db.Books.id == db.books_publishers_link.c.book, db.Publishers
    elif sort_param == "authors":
        order = [db.Authors.name.asc(), db.Series.name, db.Books.series_index] if order == "asc" \
            else [db.Authors.name.desc(), db.Series.name.desc(), db.Books.series_index.desc()]
        join = db.books_authors_link, db.Books.id == db.books_authors_link.c.book, db.Authors, db.books_series_link, \
            db.Books.id == db.books_series_link.c.book, db.Series
    elif sort_param == "languages":
        order = [db.Languages.lang_code.asc()] if order == "asc" else [db.Languages.lang_code.desc()]
        join = db.books_languages_link, db.Books.id == db.books_languages_link.c.book, db.Languages
    elif order and sort_param in ["sort", "title", "authors_sort", "series_index"]:
        order = [text(sort_param + " " + order)]
    elif not state:
        order = [db.Books.timestamp.desc()]

    total_count = filtered_count = calibre_db.session.query(db.Books).filter(
        calibre_db.common_filters(allow_show_archived=True)).count()
    if state is not None:
        if search_param:
            books = calibre_db.search_query(search_param, config).all()
            filtered_count = len(books)
        else:
            query = calibre_db.generate_linked_query(config.config_read_column, db.Books)
            books = query.filter(calibre_db.common_filters(allow_show_archived=True)).all()
        entries = calibre_db.get_checkbox_sorted(books, state, off, limit, order, True)
    elif search_param:
        entries, filtered_count, __ = calibre_db.get_search_results(search_param,
                                                                    config,
                                                                    off,
                                                                    [order, ''],
                                                                    limit,
                                                                    *join)
    else:
        entries, __, __ = calibre_db.fill_indexpage_with_archived_books((int(off) / (int(limit)) + 1),
                                                                        db.Books,
                                                                        limit,
                                                                        True,
                                                                        order,
                                                                        True,
                                                                        True,
                                                                        config.config_read_column,
                                                                        *join)

    # Fetch user preferences for books
    pref_book_ids = {}
    if current_user.is_authenticated:
         pref_book_ids = {p.item_id: p.status for p in ub.session.query(ub.UserPreference).filter(
            ub.UserPreference.user_id == current_user.id,
            ub.UserPreference.item_type == constants.ITEM_TYPE_BOOK
        ).all()}

    result = list()
    for entry in entries:
        val = entry[0]
        val.is_archived = entry[1] is True
        val.read_status = entry[2] == ub.ReadBook.STATUS_FINISHED
        val.custom_preference = pref_book_ids.get(val.id, 0)
        for lang_index in range(0, len(val.languages)):
            val.languages[lang_index].language_name = isoLanguages.get_language_name(get_locale(), val.languages[
                lang_index].lang_code)
        result.append(val)

    table_entries = {'totalNotFiltered': total_count, 'total': filtered_count, "rows": result}
    js_list = json.dumps(table_entries, cls=db.AlchemyEncoder)

    response = make_response(js_list)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


@web.route("/ajax/table_settings", methods=['POST'])
@user_login_required
def update_table_settings():
    current_user.view_settings['table'] = json.loads(request.data)
    try:
        try:
            flag_modified(current_user, "view_settings")
        except AttributeError:
            pass
        ub.session.commit()
    except (InvalidRequestError, OperationalError):
        log.error("Invalid request received: %r ", request, )
        return "Invalid request", 400
    return ""


@web.route("/author")
@login_required_if_no_ano
def author_list():
    if current_user.check_visibility(constants.SIDEBAR_AUTHOR):
        if current_user.get_view_property('author', 'dir') == 'desc':
            order = db.Authors.sort.desc()
            order_no = 0
        else:
            order = db.Authors.sort.asc()
            order_no = 1
        entries = calibre_db.session.query(db.Authors, func.count('books_authors_link.book').label('count')) \
            .join(db.books_authors_link).join(db.Books).filter(calibre_db.common_filters()) \
            .group_by(text('books_authors_link.author')).order_by(order).all()
        char_list = query_char_list(db.Authors.sort, db.books_authors_link)
        # If not creating a copy, readonly databases can not display authornames with "|" in it as changing the name
        # starts a change session
        author_copy = copy.deepcopy(entries)
        for entry in author_copy:
            entry.Authors.name = entry.Authors.name.replace('|', ',')
        
        # Fetch User Preferences for Authors
        prefs = ub.session.query(ub.UserPreference).filter(
            ub.UserPreference.user_id == current_user.id,
            ub.UserPreference.item_type == constants.ITEM_TYPE_AUTHOR
        ).all()
        pref_author_ids = {p.item_id: p.status for p in prefs}

        return render_title_template('list.html', entries=author_copy, folder='web.books_list', charlist=char_list,
                                     title="Authors", page="authorlist", data='author', order=order_no,
                                     pref_author_ids=pref_author_ids)
    else:
        abort(404)


@web.route("/downloadlist")
@login_required_if_no_ano
def download_list():
    if current_user.get_view_property('download', 'dir') == 'desc':
        order = ub.User.name.desc()
        order_no = 0
    else:
        order = ub.User.name.asc()
        order_no = 1
    if current_user.check_visibility(constants.SIDEBAR_DOWNLOAD) and current_user.role_admin():
        entries = ub.session.query(ub.User, func.count(ub.Downloads.book_id).label('count')) \
            .join(ub.Downloads).group_by(ub.Downloads.user_id).order_by(order).all()
        char_list = ub.session.query(func.upper(func.substr(ub.User.name, 1, 1)).label('char')) \
            .filter(ub.User.role.op('&')(constants.ROLE_ANONYMOUS) != constants.ROLE_ANONYMOUS) \
            .group_by(func.upper(func.substr(ub.User.name, 1, 1))).all()
        return render_title_template('list.html', entries=entries, folder='web.books_list', charlist=char_list,
                                     title=_("Downloads"), page="downloadlist", data="download", order=order_no)
    else:
        abort(404)


@web.route("/publisher")
@login_required_if_no_ano
def publisher_list():
    if current_user.get_view_property('publisher', 'dir') == 'desc':
        order = db.Publishers.name.desc()
        order_no = 0
    else:
        order = db.Publishers.name.asc()
        order_no = 1
    if current_user.check_visibility(constants.SIDEBAR_PUBLISHER):
        entries = calibre_db.session.query(db.Publishers, func.count('books_publishers_link.book').label('count')) \
            .join(db.books_publishers_link).join(db.Books).filter(calibre_db.common_filters()) \
            .group_by(text('books_publishers_link.publisher')).order_by(order).all()
        no_publisher_count = (calibre_db.session.query(db.Books)
                           .outerjoin(db.books_publishers_link).outerjoin(db.Publishers)
                           .filter(db.Publishers.name == None)
                           .filter(calibre_db.common_filters())
                           .count())
        if no_publisher_count:
            entries.append([db.Category(_("None"), "-1"), no_publisher_count])
        entries = sorted(entries, key=lambda x: x[0].name.lower(), reverse=not order_no)
        char_list = generate_char_list(entries)
        return render_title_template('list.html', entries=entries, folder='web.books_list', charlist=char_list,
                                     title=_("Publishers"), page="publisherlist", data="publisher", order=order_no)
    else:
        abort(404)


@web.route("/series")
@login_required_if_no_ano
def series_list():
    if current_user.check_visibility(constants.SIDEBAR_SERIES):
        if current_user.get_view_property('series', 'dir') == 'desc':
            order = db.Series.sort.desc()
            order_no = 0
        else:
            order = db.Series.sort.asc()
            order_no = 1
        char_list = query_char_list(db.Series.sort, db.books_series_link)
        if current_user.get_view_property('series', 'series_view') == 'list':
            entries = calibre_db.session.query(db.Series, func.count('books_series_link.book').label('count')) \
                .join(db.books_series_link).join(db.Books).filter(calibre_db.common_filters()) \
                .group_by(text('books_series_link.series')).order_by(order).all()
            no_series_count = (calibre_db.session.query(db.Books)
                            .outerjoin(db.books_series_link).outerjoin(db.Series)
                            .filter(db.Series.name == None)
                            .filter(calibre_db.common_filters())
                            .count())
            if no_series_count:
                entries.append([db.Category(_("None"), "-1"), no_series_count])
            entries = sorted(entries, key=lambda x: x[0].name.lower(), reverse=not order_no)

            # Fetch User Preferences for Series
            prefs = ub.session.query(ub.UserPreference).filter(
                ub.UserPreference.user_id == current_user.id,
                ub.UserPreference.item_type == constants.ITEM_TYPE_SERIES
            ).all()
            pref_series_ids = {p.item_id: p.status for p in prefs}

            return render_title_template('list.html',
                                         entries=entries,
                                         folder='web.books_list',
                                         charlist=char_list,
                                         title=_("Series"),
                                         page="serieslist",
                                         data="series", order=order_no,
                                         pref_series_ids=pref_series_ids)
        else:
            entries = (calibre_db.session.query(db.Books, func.count('books_series_link').label('count'),
                                                func.max(db.Books.series_index), db.Books.id)
                       .join(db.books_series_link).join(db.Series).filter(calibre_db.common_filters())
                       .group_by(text('books_series_link.series'))
                       .having(or_(func.max(db.Books.series_index), db.Books.series_index==""))
                       .order_by(order)
                       .all())

            # Fetch User Preferences for Series
            prefs = ub.session.query(ub.UserPreference).filter(
                ub.UserPreference.user_id == current_user.id,
                ub.UserPreference.item_type == constants.ITEM_TYPE_SERIES
            ).all()
            pref_series_ids = {p.item_id: p.status for p in prefs}

            return render_title_template('grid.html', entries=entries, folder='web.books_list', charlist=char_list,
                                         title=_("Series"), page="serieslist", data="series", bodyClass="grid-view",
                                         order=order_no, pref_series_ids=pref_series_ids)
    else:
        abort(404)


@web.route("/series-tracker")
@login_required_if_no_ano
def series_tracker():
    if not current_user.check_visibility(constants.SIDEBAR_SERIES_TRACKER):
        abort(404)
    
    # Query all books with series
    all_books = calibre_db.session.query(db.Books).join(db.books_series_link).join(db.Series).filter(calibre_db.common_filters()).all()
    
    # Fetch read status for current user
    read_books = ub.session.query(ub.ReadBook).filter(ub.ReadBook.user_id == int(current_user.id)).all()
    read_info_map = {rb.book_id: {'status': rb.read_status, 'progress': rb.progress_percent} for rb in read_books}

    series_data = {}
    for book in all_books:
        if not book.series:
            continue
        for s in book.series:
            series_name = s.name
            if series_name not in series_data:
                series_data[series_name] = {
                    'id': s.id, 
                    'name': s.name, 
                    'books': [], 
                    'indices': set(), 
                    'read_indices': set(), 
                    'all_healthy': True,
                    'read_count': 0
                }
            
            info = read_info_map.get(book.id, {'status': ub.ReadBook.STATUS_UNREAD, 'progress': 0.0})
            book.read_status = info['status']
            book.progress_percent = info['progress']
            
            series_data[series_name]['books'].append(book)
            
            # Health check from cache or quick audit
            # (Note: in a large library, getting health for every book might be slow, but we'll stick to the current pattern)
            health = audit_helper.get_book_health(book, config.get_book_path(), quick=True)
            if not health['is_healthy']:
                series_data[series_name]['all_healthy'] = False

            try:
                val = float(book.series_index)
                series_data[series_name]['indices'].add(val)
                if book.read_status == ub.ReadBook.STATUS_FINISHED:
                    series_data[series_name]['read_indices'].add(val)
                    series_data[series_name]['read_count'] += 1
            except (ValueError, TypeError):
                pass

    results = []
    for name, data in series_data.items():
        if not data['indices']:
            continue
        
        indices = sorted(list(data['indices']))
        read_indices = sorted(list(data['read_indices']))
        min_idx = int(min(indices))
        max_idx = int(max(indices))
        total_count = len(indices)
        read_count = len(read_indices)
        
        gaps = []
        for i in range(min_idx, max_idx + 1):
            found = False
            for idx in indices:
                if i <= idx < i + 1:
                    found = True
                    break
            if not found:
                gaps.append(i)
        
        has_new_books = False
        is_update_available = False # Special alert for "Series I've read but has new items"
        
        if read_indices:
            max_read = max(read_indices)
            if max_idx > max_read:
                has_new_books = True
                
                # Check if everything <= max_read is read
                all_before_max_read_done = True
                for idx in indices:
                    if idx <= max_read and idx not in read_indices:
                        all_before_max_read_done = False
                        break
                if all_before_max_read_done:
                    is_update_available = True
        
        results.append({
            'name': name,
            'id': data['id'],
            'count': len(data['books']),
            'total_in_series': total_count,
            'read_count': read_count,
            'min': min_idx,
            'max': max_idx,
            'gaps': gaps,
            'is_complete': len(gaps) == 0,
            'has_new_books': has_new_books,
            'is_update_available': is_update_available,
            'is_fully_read': read_count == total_count,
            'all_healthy': data['all_healthy'],
            'books': sorted(data['books'], key=lambda x: float(x.series_index) if x.series_index else 0)
        })
    
    results.sort(key=lambda x: x['name'])
    
    return render_title_template('series_tracker.html', series=results, title=_("Series Tracker"), page="series_tracker")


@web.route("/series/mark-read/<int:series_id>")
@user_login_required
def mark_series_read(series_id):
    books = calibre_db.session.query(db.Books).join(db.books_series_link).filter(db.books_series_link.c.series == series_id).all()
    for book in books:
        edit_book_read_status(book.id, read_status=True)
    flash(_("Series marked as read"), category="success")
    return redirect(request.referrer or url_for('web.index'))


@web.route("/series/bulk-download/<int:series_id>")
@user_login_required
def bulk_download_series(series_id):
    s = calibre_db.session.query(db.Series).filter(db.Series.id == series_id).first()
    if not s:
        abort(404)
    books = calibre_db.session.query(db.Books).join(db.books_series_link).filter(db.books_series_link.c.series == series_id).all()
    book_ids = [b.id for b in books]
    author_name = _("Unknown")
    if books and books[0].authors:
        author_name = books[0].authors[0].name
    zip_filename = get_valid_filename(u"{} - {}".format(author_name, s.name)) + ".zip"
    task = TaskBulkDownload(_("Downloading series: {}").format(s.name), book_ids, zip_filename, current_user.id)
    WorkerThread.add(current_user.id, task)
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': _("Preparing ZIP file for series: {}").format(s.name)
        })
    
    flash(_("Bulk download started. Check 'Tasks' for the ZIP link."), category="info")
    return redirect(request.referrer or url_for('web.index'))

@web.route("/download-bulk/<filename>")
@user_login_required
def download_bulk_file(filename):
    if not re.match(r"^[a-zA-Z0-9_\-\. ]+\.zip$", filename):
        abort(403)
    folder = os.path.join(config.config_calibre_dir, "downloads")
    return send_from_directory(folder, filename, as_attachment=True)


@web.route("/author-dashboard")
@login_required_if_no_ano
def author_dashboard():
    if not current_user.check_visibility(constants.SIDEBAR_AUTHOR_DASHBOARD):
        abort(404)
    
    show_filter = request.args.get('filter', 'all')
    
    # Query all books with authors
    all_books = calibre_db.session.query(db.Books).join(db.books_authors_link).join(db.Authors).filter(calibre_db.common_filters()).all()
    
    # Fetch all health cache data
    health_cache = {h.book_id: h for h in ub.session.query(ub.BookHealth).all()}
    
    # Fetch reading progress for current user
    read_progress = {r.book_id: r for r in ub.session.query(ub.ReadBook).filter(ub.ReadBook.user_id == int(current_user.id)).all()}
    
    last_scan = ub.session.query(func.max(ub.BookHealth.last_scan)).scalar()

    author_data = {}
    for book in all_books:
        for a in book.authors:
            if a.name not in author_data:
                author_data[a.name] = {'id': a.id, 'name': a.name, 'series': {}, 'all_healthy': True, 'count_issues': 0}
            
            # Get book health from cache
            cache_info = health_cache.get(book.id)
            if cache_info:
                health = {
                    'is_healthy': cache_info.is_healthy,
                    'has_azw': cache_info.has_azw,
                    'has_epub': cache_info.has_epub,
                    'has_docx_cz': cache_info.has_docx_cz,
                    'extra_formats': cache_info.extra_formats,
                    'desc_lang': cache_info.desc_lang
                }
            else:
                health = {'is_healthy': True, 'has_azw': True, 'has_epub': True, 'has_docx_cz': True, 'extra_formats': [], 'desc_lang': 'ces'}
            
            book.health = health
            
            # Get reading progress
            progress = read_progress.get(book.id)
            if progress:
                book.read_status = progress.read_status
                book.progress_percent = progress.progress_percent
            else:
                book.read_status = ub.ReadBook.STATUS_UNREAD
                book.progress_percent = 0.0
            
            if not health['is_healthy']:
                author_data[a.name]['all_healthy'] = False
                author_data[a.name]['count_issues'] += 1

            series_name = _("No Series")
            series_id = -1
            if book.series:
                series_name = book.series[0].name
                series_id = book.series[0].id
            
            if series_name not in author_data[a.name]['series']:
                author_data[a.name]['series'][series_name] = {'id': series_id, 'books': [], 'all_healthy': True, 'gaps': []}
            
            author_data[a.name]['series'][series_name]['books'].append(book)
            if not health['is_healthy']:
                author_data[a.name]['series'][series_name]['all_healthy'] = False

    # Convert dictionary to sorted list of authors
    sorted_authors = []
    for a_name in sorted(author_data.keys()):
        a_info = author_data[a_name]
        
        # Apply filter: if 'issues' only show authors with issues
        if show_filter == 'issues' and a_info['all_healthy']:
            continue

        sorted_series = []
        
        # Get "No Series" if exists
        no_series_info = a_info['series'].pop(_("No Series"), None)
        
        for s_name in sorted(a_info['series'].keys()):
            s_data = a_info['series'][s_name]
            s_data['books'].sort(key=lambda x: float(x.series_index) if x.series_index else 0)
            
            # Calculate gaps
            indices = sorted([int(float(b.series_index)) for b in s_data['books'] if b.series_index])
            if indices:
                for i in range(1, max(indices) + 1):
                    if i not in indices:
                        s_data['gaps'].append(i)
            
            # Update alert logic
            read_indices = [float(b.series_index) for b in s_data['books'] if b.series_index and b.read_status == ub.ReadBook.STATUS_FINISHED]
            s_data['is_update_available'] = False
            if read_indices:
                max_read = max(read_indices)
                all_indices = [float(b.series_index) for b in s_data['books'] if b.series_index]
                max_exists = max(all_indices)
                if max_exists > max_read:
                    # Check if all below max_read are read
                    all_before_done = True
                    for b in s_data['books']:
                        if b.series_index:
                            idx = float(b.series_index)
                            if idx <= max_read and b.read_status != ub.ReadBook.STATUS_FINISHED:
                                all_before_done = False
                                break
                    if all_before_done:
                        s_data['is_update_available'] = True

            sorted_series.append({
                'name': s_name, 
                'id': s_data['id'], 
                'books': s_data['books'], 
                'all_healthy': s_data['all_healthy'],
                'gaps': s_data['gaps'],
                'is_update_available': s_data['is_update_available']
            })
            
        if no_series_info:
            no_series_info['books'].sort(key=lambda x: x.title)
            sorted_series.append({
                'name': _("No Series"), 
                'id': -1, 
                'books': no_series_info['books'], 
                'all_healthy': no_series_info['all_healthy'],
                'gaps': []
            })
            
        sorted_authors.append({
            'name': a_name,
            'id': a_info['id'],
            'series': sorted_series,
            'all_healthy': a_info['all_healthy'],
            'count_issues': a_info['count_issues']
        })

    return render_title_template('author_dashboard.html', 
                               authors=sorted_authors, 
                               last_scan=last_scan,
                               current_filter=show_filter,
                               title=_("Author Dashboard"), 
                               page="author_dashboard")


@web.route("/author-dashboard/refresh")
@user_login_required
def author_dashboard_refresh():
    if not current_user.role_admin():
        abort(403)
    from .tasks.author import TaskRefreshAuthorDashboard
    task = TaskRefreshAuthorDashboard()
    WorkerThread.add(current_user.id, task)
    flash(_("Library health refresh started in background"), category="success")
    return redirect(url_for('web.author_dashboard'))


@web.route("/author-dashboard/refresh-status")
@user_login_required
def author_dashboard_refresh_status():
    """AJAX endpoint to check health refresh task progress"""
    from .services.worker import STAT_WAITING, STAT_STARTED, STAT_FINISH_SUCCESS, STAT_FAIL, STAT_ENDED, STAT_CANCELLED
    
    worker = WorkerThread.get_instance()
    tasks = worker.tasks if worker else []
    
    # Find the most recent health refresh task for this user
    for task in reversed(tasks):
        if task.get('user') == current_user.id and 'TaskRefreshAuthorDashboard' in str(task.get('task', '')):
            t = task.get('task')
            if t:
                progress = int(t.progress * 100) if hasattr(t, 'progress') else 0
                status = t.stat if hasattr(t, 'stat') else 0
                
                is_running = status in (STAT_WAITING, STAT_STARTED)
                is_complete = status == STAT_FINISH_SUCCESS
                is_failed = status in (STAT_FAIL, STAT_ENDED, STAT_CANCELLED)
                
                return jsonify({
                    'running': is_running,
                    'complete': is_complete,
                    'failed': is_failed,
                    'progress': progress,
                    'message': str(t.message) if hasattr(t, 'message') else ''
                })
    
    return jsonify({'running': False, 'complete': False, 'failed': False, 'progress': 0, 'message': ''})


@web.route("/author/mark-read/<int:author_id>")
@user_login_required
def mark_author_read(author_id):
    books = calibre_db.session.query(db.Books).join(db.books_authors_link).filter(db.books_authors_link.c.author == author_id).all()
    for book in books:
        edit_book_read_status(book.id, read_status=True)
    flash(_("All books by author marked as read"), category="success")
    return redirect(request.referrer or url_for('web.index'))

@web.route("/author/bulk-download/<int:author_id>")
@user_login_required
def bulk_download_author(author_id):
    a = calibre_db.session.query(db.Authors).filter(db.Authors.id == author_id).first()
    if not a:
        abort(404)
    books = calibre_db.session.query(db.Books).join(db.books_authors_link).filter(db.books_authors_link.c.author == author_id).all()
    book_ids = [b.id for b in books]
    zip_filename = get_valid_filename(a.name) + ".zip"
    task = TaskBulkDownload(_("Downloading all books by author: {}").format(a.name), book_ids, zip_filename, current_user.id)
    WorkerThread.add(current_user.id, task)
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': _("Preparing ZIP file for author: {}").format(a.name)
        })
    
    flash(_("Bulk download started. Check 'Tasks' for the ZIP link."), category="info")
    return redirect(request.referrer or url_for('web.index'))


@web.route("/ratings")
@login_required_if_no_ano
def ratings_list():
    if current_user.check_visibility(constants.SIDEBAR_RATING):
        if current_user.get_view_property('ratings', 'dir') == 'desc':
            order = db.Ratings.rating.desc()
            order_no = 0
        else:
            order = db.Ratings.rating.asc()
            order_no = 1
        entries = calibre_db.session.query(db.Ratings, func.count('books_ratings_link.book').label('count'),
                                           (db.Ratings.rating / 2).label('name')) \
            .join(db.books_ratings_link).join(db.Books).filter(calibre_db.common_filters()) \
            .filter(db.Ratings.rating > 0) \
            .group_by(text('books_ratings_link.rating')).order_by(order).all()
        no_rating_count = (calibre_db.session.query(db.Books)
                           .outerjoin(db.books_ratings_link).outerjoin(db.Ratings)
                           .filter(or_(db.Ratings.rating == None, db.Ratings.rating == 0))
                           .filter(calibre_db.common_filters())
                           .count())
        if no_rating_count:
            entries.append([db.Category(_("None"), "-1", -1), no_rating_count])
        entries = sorted(entries, key=lambda x: x[0].rating, reverse=not order_no)

        # Fetch User Preferences for Books if viewing books/formats? No, this is rating list.
        # But wait, User requested "u knih... chybi moznost oznaceni".
        # Ratings list displays rating categories, not books directly. Ignored.
        
        return render_title_template('list.html', entries=entries, folder='web.books_list', charlist=list(),
                                     title=_("Ratings list"), page="ratingslist", data="ratings", order=order_no)
    else:
        abort(404)


@web.route("/formats")
@login_required_if_no_ano
def formats_list():
    if current_user.check_visibility(constants.SIDEBAR_FORMAT):
        if current_user.get_view_property('formats', 'dir') == 'desc':
            order = db.Data.format.desc()
            order_no = 0
        else:
            order = db.Data.format.asc()
            order_no = 1
        entries = calibre_db.session.query(db.Data,
                                           func.count('data.book').label('count'),
                                           db.Data.format.label('format')) \
            .join(db.Books).filter(calibre_db.common_filters()) \
            .group_by(db.Data.format).order_by(order).all()
        no_format_count = (calibre_db.session.query(db.Books).outerjoin(db.Data)
                           .filter(db.Data.format == None)
                           .filter(calibre_db.common_filters())
                           .count())
        if no_format_count:
            entries.append([db.Category(_("None"), "-1"), no_format_count])
        return render_title_template('list.html', entries=entries, folder='web.books_list', charlist=list(),
                                     title=_("File formats list"), page="formatslist", data="formats", order=order_no)
    else:
        abort(404)


@web.route("/language")
@login_required_if_no_ano
def language_overview():
    if current_user.check_visibility(constants.SIDEBAR_LANGUAGE) and current_user.filter_language() == "all":
        order_no = 0 if current_user.get_view_property('language', 'dir') == 'desc' else 1
        languages = calibre_db.speaking_language(reverse_order=not order_no, with_count=True)
        char_list = generate_char_list(languages)
        return render_title_template('list.html', entries=languages, folder='web.books_list', charlist=char_list,
                                     title=_("Languages"), page="langlist", data="language", order=order_no)
    else:
        abort(404)


@web.route("/category")
@login_required_if_no_ano
def category_list():
    if current_user.check_visibility(constants.SIDEBAR_CATEGORY):
        if current_user.get_view_property('category', 'dir') == 'desc':
            order = db.Tags.name.desc()
            order_no = 0
        else:
            order = db.Tags.name.asc()
            order_no = 1
        entries = calibre_db.session.query(db.Tags, func.count('books_tags_link.book').label('count')) \
            .join(db.books_tags_link).join(db.Books).order_by(order).filter(calibre_db.common_filters()) \
            .filter(db.Tags.name.notlike('docID:%')) \
            .group_by(db.Tags.id).all()
        no_tag_count = (calibre_db.session.query(db.Books)
                         .outerjoin(db.books_tags_link).outerjoin(db.Tags)
                        .filter(db.Tags.name == None)
                         .filter(calibre_db.common_filters())
                         .count())
        if no_tag_count:
            entries.append([db.Category(_("None"), "-1"), no_tag_count])
        entries = sorted(entries, key=lambda x: x[0].name.lower(), reverse=not order_no)
        char_list = generate_char_list(entries)
        return render_title_template('list.html', entries=entries, folder='web.books_list', charlist=char_list,
                                     title=_("Categories"), page="catlist", data="category", order=order_no)
    else:
        abort(404)





@web.route("/ignored")
@login_required_if_no_ano
def ignored_list():
    prefs = ub.session.query(ub.UserPreference).filter(
        ub.UserPreference.user_id == int(current_user.id),
        ub.UserPreference.status == -1
    ).all()

    book_ids = [p.item_id for p in prefs if p.item_type == constants.ITEM_TYPE_BOOK]
    series_ids = [p.item_id for p in prefs if p.item_type == constants.ITEM_TYPE_SERIES]
    author_ids = [p.item_id for p in prefs if p.item_type == constants.ITEM_TYPE_AUTHOR]

    books = []
    if book_ids:
        books = calibre_db.session.query(db.Books).filter(db.Books.id.in_(book_ids)).all()

    series = []
    if series_ids:
        series = calibre_db.session.query(db.Series).filter(db.Series.id.in_(series_ids)).all()

    authors = []
    if author_ids:
        authors = calibre_db.session.query(db.Authors).filter(db.Authors.id.in_(author_ids)).all()

    return render_title_template('ignored.html', books=books, series=series, authors=authors, title=_("Ignored Items"), page="ignored")


@web.route("/preferred")
@login_required_if_no_ano
def preferred_list():
    prefs = ub.session.query(ub.UserPreference).filter(
        ub.UserPreference.user_id == int(current_user.id),
        ub.UserPreference.status == 1
    ).all()

    book_ids = [p.item_id for p in prefs if p.item_type == constants.ITEM_TYPE_BOOK]
    series_ids = [p.item_id for p in prefs if p.item_type == constants.ITEM_TYPE_SERIES]
    author_ids = [p.item_id for p in prefs if p.item_type == constants.ITEM_TYPE_AUTHOR]

    books = []
    if book_ids:
        books = calibre_db.session.query(db.Books).filter(db.Books.id.in_(book_ids)).all()

    series = []
    if series_ids:
        series = calibre_db.session.query(db.Series).filter(db.Series.id.in_(series_ids)).all()

    authors = []
    if author_ids:
        authors = calibre_db.session.query(db.Authors).filter(db.Authors.id.in_(author_ids)).all()

    return render_title_template('preferred.html', books=books, series=series, authors=authors, title=_("Preferred Items"), page="preferred")


# ################################### Download/Send ##################################################################


@web.route("/cover/<int:book_id>")
@web.route("/cover/<int:book_id>/<string:resolution>")
@login_required_if_no_ano
def get_cover(book_id, resolution=None):
    resolutions = {
        'og': constants.COVER_THUMBNAIL_ORIGINAL,
        'sm': constants.COVER_THUMBNAIL_SMALL,
        'md': constants.COVER_THUMBNAIL_MEDIUM,
        'lg': constants.COVER_THUMBNAIL_LARGE,
    }
    cover_resolution = resolutions.get(resolution, None)
    return get_book_cover(book_id, cover_resolution)


@web.route("/series_cover/<int:series_id>")
@web.route("/series_cover/<int:series_id>/<string:resolution>")
@login_required_if_no_ano
def get_series_cover(series_id, resolution=None):
    resolutions = {
        'og': constants.COVER_THUMBNAIL_ORIGINAL,
        'sm': constants.COVER_THUMBNAIL_SMALL,
        'md': constants.COVER_THUMBNAIL_MEDIUM,
        'lg': constants.COVER_THUMBNAIL_LARGE,
    }
    cover_resolution = resolutions.get(resolution, None)
    return get_series_cover_thumbnail(series_id, cover_resolution)


@web.route("/toggle_view_mode")
@user_login_required
def toggle_view_mode():
    if not current_user.real_role_admin():
         abort(403)
    
    if flask_session.get('guest_view_mode'):
        flask_session.pop('guest_view_mode', None)
        flash(_('Switched to Admin View'), category="info")
    else:
        flask_session['guest_view_mode'] = True
        flash(_('Switched to Guest View'), category="info")
        
    return redirect(request.referrer or url_for('web.index'))



@web.route("/robots.txt")
def get_robots():
    try:
        return send_from_directory(constants.STATIC_DIR, "robots.txt")
    except PermissionError:
        log.error("No permission to access robots.txt file.")
        abort(403)


@web.route("/show/<int:book_id>/<book_format>", defaults={'anyname': 'None'})
@web.route("/show/<int:book_id>/<book_format>/<anyname>")
@login_required_if_no_ano
@viewer_required
def serve_book(book_id, book_format, anyname):
    book_format = book_format.split(".")[0]
    book = calibre_db.get_book(book_id)
    data = calibre_db.get_book_format(book_id, book_format.upper())
    if not data:
        return "File not in Database"
    range_header = request.headers.get('Range', None)
    if not range_header:
        log.info('Serving book: \'%s\' to %s - %s', data.name, current_user.name,
                 request.headers.get('X-Forwarded-For', request.remote_addr))
    if config.config_use_google_drive:
        try:
            headers = Headers()
            headers["Content-Type"] = mimetypes.types_map.get('.' + book_format, "application/octet-stream")
            if not range_header:                
                headers['Accept-Ranges'] = 'bytes'
            df = getFileFromEbooksFolder(book.path, data.name + "." + book_format)
            return do_gdrive_download(df, headers, (book_format.upper() == 'TXT'))
        except AttributeError as ex:
            log.error_or_exception(ex)
            return "File Not Found"
    else:
        if book_format.upper() == 'TXT':
            try:
                rawdata = open(os.path.join(config.get_book_path(), book.path, data.name + "." + book_format),
                               "rb").read()
                result = chardet.detect(rawdata)
                try:
                    text_data = rawdata.decode(result['encoding']).encode('utf-8')
                except UnicodeDecodeError as e:
                    log.error("Encoding error in text file {}: {}".format(book.id, e))
                    if "surrogate" in e.reason:
                        text_data = rawdata.decode(result['encoding'], 'surrogatepass').encode('utf-8', 'surrogatepass')
                    else:
                        text_data = rawdata.decode(result['encoding'], 'ignore').encode('utf-8', 'ignore')
                return make_response(text_data)
            except FileNotFoundError:
                log.error("File Not Found")
                return "File Not Found"
        # enable byte range read of pdf
        response = make_response(
            send_from_directory(os.path.join(config.get_book_path(), book.path), data.name + "." + book_format))
        if not range_header:
            response.headers['Accept-Ranges'] = 'bytes'
        return response


@web.route("/download/<int:book_id>/<book_format>", defaults={'anyname': 'None'})
@web.route("/download/<int:book_id>/<book_format>/<anyname>")
@login_required_if_no_ano
@download_required
def download_link(book_id, book_format, anyname):
    if "kindle" in request.headers.get('User-Agent').lower():
        client = "kindle"
    elif "Kobo" in request.headers.get('User-Agent').lower():
        client = "kobo"
    else:
        client = ""
    return get_download_link(book_id, book_format, client)


@web.route('/send/<int:book_id>/<book_format>/<int:convert>', methods=["POST"])
@login_required_if_no_ano
@download_required
def send_to_ereader(book_id, book_format, convert):
    if not config.get_mail_server_configured():
        return make_response(jsonify(type="danger", message=_("Please configure the SMTP mail settings first...")))
    elif current_user.kindle_mail:
        result = send_mail(book_id, book_format, convert, current_user.kindle_mail, config.get_book_path(),
                           current_user.name)
        if result is None:
            ub.update_download(book_id, int(current_user.id))
            response = [{'type': "success", 'message': _("Success! Book queued for sending to %(eReadermail)s",
                                                       eReadermail=current_user.kindle_mail)}]
        else:
            response = [{'type': "danger", 'message': _("Oops! There was an error sending book: %(res)s", res=result)}]
    else:
        response = [{'type': "danger", 'message': _("Oops! Please update your profile with a valid eReader Email.")}]
    return make_response(jsonify(response))


# ################################### Login Logout ##################################################################

@web.route('/register', methods=['POST'])
@limiter.limit("40/day", key_func=get_remote_address)
@limiter.limit("3/minute", key_func=get_remote_address)
def register_post():
    if not config.config_public_reg:
        abort(404)
    to_save = request.form.to_dict()
    try:
        limiter.check()
    except RateLimitExceeded:
        flash(_(u"Please wait one minute to register next user"), category="error")
        return render_title_template('register.html', config=config, title=_("Register"), page="register")
    except (ConnectionError, Exception) as e:
        log.error("Connection error to limiter backend: %s", e)
        flash(_("Connection error to limiter backend, please contact your administrator"), category="error")
        return render_title_template('register.html', config=config, title=_("Register"), page="register")
    if current_user is not None and current_user.is_authenticated:
        return redirect(url_for('web.index'))
    if not config.get_mail_server_configured():
        flash(_("Oops! Email server is not configured, please contact your administrator."), category="error")
        return render_title_template('register.html', title=_("Register"), page="register")
    nickname = strip_whitespaces(to_save.get("email", "")) if config.config_register_email else to_save.get('name')
    if not nickname or not to_save.get("email"):
        flash(_("Oops! Please complete all fields."), category="error")
        return render_title_template('register.html', title=_("Register"), page="register")
    try:
        nickname = check_username(nickname)
        email = check_email(to_save.get("email", ""))
    except Exception as ex:
        flash(str(ex), category="error")
        return render_title_template('register.html', title=_("Register"), page="register")

    content = ub.User()
    if check_valid_domain(email):
        content.name = nickname
        content.email = email
        password = generate_random_password(config.config_password_min_length)
        content.password = generate_password_hash(password)
        content.role = config.config_default_role
        content.locale = config.config_default_locale
        content.sidebar_view = config.config_default_show
        content.set_view_property('user', 'theme', to_save.get('theme', 'ca_black'))
        try:
            ub.session.add(content)
            ub.session.commit()
            if feature_support['oauth']:
                register_user_with_oauth(content)
            send_registration_mail(strip_whitespaces(to_save.get("email", "")), nickname, password)
        except Exception:
            ub.session.rollback()
            flash(_("Oops! An unknown error occurred. Please try again later."), category="error")
            return render_title_template('register.html', title=_("Register"), page="register")
    else:
        flash(_("Oops! Your Email is not allowed."), category="error")
        log.warning('Registering failed for user "{}" Email: {}'.format(nickname, to_save.get("email","")))
        return render_title_template('register.html', title=_("Register"), page="register")
    flash(_("Success! Confirmation Email has been sent."), category="success")
    return redirect(url_for('web.login'))


@web.route('/register', methods=['GET'])
def register():
    if not config.config_public_reg:
        abort(404)
    if current_user is not None and current_user.is_authenticated:
        return redirect(url_for('web.index'))
    if not config.get_mail_server_configured():
        flash(_("Oops! Email server is not configured, please contact your administrator."), category="error")
        return render_title_template('register.html', title=_("Register"), page="register")
    if feature_support['oauth']:
        register_user_with_oauth()
    return render_title_template('register.html', config=config, title=_("Register"), page="register")


def handle_login_user(user, remember, message, category):
    login_user(user, remember=remember)
    flash(message, category=category)
    [limiter.limiter.storage.clear(k.key) for k in limiter.current_limits]
    return redirect(get_redirect_location(request.form.get('next', None), "web.index"))


def render_login(username="", password=""):
    next_url = request.args.get('next', default=url_for("web.index"), type=str)
    if url_for("web.logout") == next_url:
        next_url = url_for("web.index")
    return render_title_template('login.html',
                                 title=_("Login"),
                                 next_url=next_url,
                                 config=config,
                                 username=username,
                                 password=password,
                                 oauth_check=oauth_check,
                                 mail=config.get_mail_server_configured(), page="login")


@web.route('/login', methods=['GET'])
def login():
    if current_user is not None and current_user.is_authenticated:
        return redirect(url_for('web.index'))
    if config.config_login_type == constants.LOGIN_LDAP and not services.ldap:
        log.error(u"Cannot activate LDAP authentication")
        flash(_(u"Cannot activate LDAP authentication"), category="error")
    return render_login()


@web.route('/login', methods=['POST'])
@limiter.limit("40/day", key_func=lambda: strip_whitespaces(request.form.get('username', "")).lower())
@limiter.limit("3/minute", key_func=lambda: strip_whitespaces(request.form.get('username', "")).lower())
def login_post():
    form = request.form.to_dict()
    username = strip_whitespaces(form.get('username', "")).lower().replace("\n","").replace("\r","")
    try:
        limiter.check()
    except RateLimitExceeded:
        flash(_("Please wait one minute before next login"), category="error")
        return render_login(username, form.get("password", ""))
    except (ConnectionError, Exception) as e:
        log.error("Connection error to limiter backend: %s", e)
        flash(_("Connection error to limiter backend, please contact your administrator"), category="error")
        return render_login(username, form.get("password", ""))
    if current_user is not None and current_user.is_authenticated:
        return redirect(url_for('web.index'))
    if config.config_login_type == constants.LOGIN_LDAP and not services.ldap:
        log.error(u"Cannot activate LDAP authentication")
        flash(_(u"Cannot activate LDAP authentication"), category="error")
    user = ub.session.query(ub.User).filter(func.lower(ub.User.name) == username).first()
    remember_me = bool(form.get('remember_me'))

    # phpBB Authentication Bridge with Approval Workflow
    phpbb_conf = load_phpbb_config()
    if phpbb_conf:
        from .password_validator import validate_password_strength, get_password_requirements
        from datetime import timedelta
        
        auth = phpBBAuth(phpbb_conf)
        phpbb_user = auth.authenticate(username, form['password'])
        
        if phpbb_user:
            # Step 1: Validate password strength
            is_valid, errors = validate_password_strength(form['password'])
            if not is_valid:
                return render_title_template('weak_password.html',
                                            title=_(u"Weak Password"),
                                            password_rules=get_password_requirements())
            
            # Step 2: Check for blocked/rejected status
            rejected = ub.session.query(ub.RejectedAccess).filter_by(
                phpbb_user_id=phpbb_user['id']
            ).first()
            
            if rejected:
                if rejected.blocked:
                    # Permanently blocked after 3+ rejections
                    return render_title_template('blocked.html',
                                                title=_(u"Access Blocked"))
                else:
                    # Check cooldown (30 days)
                    cooldown_end = rejected.last_rejection_at + timedelta(days=30)
                    if datetime.now(timezone.utc) < cooldown_end:
                        return render_title_template('cooldown.html',
                                                    title=_(u"Request Rejected"),
                                                    rejection_reason=rejected.rejection_reason,
                                                    cooldown_end_date=cooldown_end.strftime('%Y-%m-%d'))
                    else:
                        # Cooldown expired, delete old rejection record
                        ub.session.delete(rejected)
                        ub.session.commit()
            
            # Step 3: Check if user already exists in Calibre-Web
            if user:
                return handle_login_user(user, remember_me,
                                        _(u"Přihlášen jako: '%(nickname)s' (phpBB)", nickname=user.name),
                                        "success")
            
            # Step 4: Check for existing pending request
            existing_request = ub.session.query(ub.AccessRequest).filter_by(
                phpbb_user_id=phpbb_user['id']
            ).first()
            
            if existing_request:
                # Request already pending
                return render_title_template('pending_approval.html',
                                            title=_(u"Request Pending"))
            
            # Step 5: Create new access request
            try:
                new_request = ub.AccessRequest()
                new_request.phpbb_user_id = phpbb_user['id']
                new_request.username = phpbb_user['username']
                new_request.email = phpbb_user['email']
                ub.session.add(new_request)
                ub.session.commit()
                log.info("New access request created for phpBB user: %s", phpbb_user['username'])
                return render_title_template('pending_approval.html',
                                            title=_(u"Request Submitted"))
            except Exception as e:
                ub.session.rollback()
                log.error("Failed to create access request: %s", e)
                flash(_(u"Chyba při vytváření žádosti."), category="error")

    if config.config_login_type == constants.LOGIN_LDAP and services.ldap and user and form['password'] != "":
        login_result, error = services.ldap.bind_user(username, form['password'])
        if login_result:
            log.debug(u"You are now logged in as: '{}'".format(user.name))
            return handle_login_user(user,
                                     remember_me,
                                     _(u"you are now logged in as: '%(nickname)s'", nickname=user.name),
                                     "success")
        elif login_result is None and user and check_password_hash(str(user.password), form['password']) \
                and user.name != "Guest":
            log.info("Local Fallback Login as: '{}'".format(user.name))
            return handle_login_user(user,
                                     remember_me,
                                     _(u"Fallback Login as: '%(nickname)s', "
                                       u"LDAP Server not reachable, or user not known", nickname=user.name),
                                     "warning")
        elif login_result is None:
            log.info(error)
            flash(_(u"Could not login: %(message)s", message=error), category="error")
        else:
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            log.warning('LDAP Login failed for user "%s" IP-address: %s', username, ip_address)
            flash(_(u"Wrong Username or Password"), category="error")
    else:
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if form.get('forgot', "") == 'forgot':
            if user is not None and user.name != "Guest":
                ret, __ = reset_password(user.id)
                if ret == 1:
                    flash(_(u"New Password was sent to your email address"), category="info")
                    log.info('Password reset for user "%s" IP-address: %s', username, ip_address)
                else:
                    log.error(u"An unknown error occurred. Please try again later")
                    flash(_(u"An unknown error occurred. Please try again later."), category="error")
            else:
                flash(_(u"Please enter valid username to reset password"), category="error")
                log.warning('Username missing for password reset IP-address: %s', ip_address)
        else:
            if user and check_password_hash(str(user.password), form['password']) and user.name != "Guest":
                config.config_is_initial = False
                log.debug(u"You are now logged in as: '{}'".format(user.name))
                return handle_login_user(user,
                                         remember_me,
                                         _(u"You are now logged in as: '%(nickname)s'", nickname=user.name),
                                         "success")
            else:
                log.warning('Login failed for user "{}" IP-address: {}'.format(username, ip_address))
                flash(_(u"Wrong Username or Password"), category="error")
    return render_login(username, form.get("password", ""))


@web.route('/logout')
@user_login_required
def logout():
    if current_user is not None and current_user.is_authenticated:
        ub.delete_user_session(current_user.id, flask_session.get('_id', ""))
        logout_user()
        if feature_support['oauth'] and (config.config_login_type == 2 or config.config_login_type == 3):
            logout_oauth_user()
    log.debug("User logged out")
    if config.config_anonbrowse:
        location = get_redirect_location(request.args.get('next', None), "web.login")
    else:
        location = None
    if location:
        return redirect(location)
    else:
        return redirect(url_for('web.login'))


# ################################### Users own configuration #########################################################
def change_profile(kobo_support, local_oauth_check, oauth_status, translations, languages):
    to_save = request.form.to_dict()
    current_user.random_books = 0
    try:
        if current_user.role_passwd() or current_user.role_admin():
            if to_save.get("password", "") != "":
                current_user.password = generate_password_hash(valid_password(to_save.get("password")))
        if to_save.get("kindle_mail", current_user.kindle_mail) != current_user.kindle_mail:
            current_user.kindle_mail = valid_email(to_save.get("kindle_mail"))
        new_email = valid_email(to_save.get("email", current_user.email))
        if not new_email:
            raise Exception(_("Email can't be empty and has to be a valid Email"))
        if new_email != current_user.email:
            current_user.email = check_email(new_email)
        if current_user.role_admin():
            if to_save.get("name", current_user.name) != current_user.name:
                # Query username, if not existing, change
                current_user.name = check_username(to_save.get("name"))
        current_user.random_books = 1 if to_save.get("show_random") == "on" else 0
        current_user.default_language = to_save.get("default_language", "all")
        current_user.locale = to_save.get("locale", "en")
        current_user.webhook_url = to_save.get("webhook_url", "")
        current_user.webhook_enabled = True if to_save.get("webhook_enabled") == "on" else False
        current_user.set_view_property('user', 'theme', to_save.get('theme', 'ca_black'))
        current_user.mobile_sync_path = to_save.get("mobile_sync_path", "")
        old_state = current_user.kobo_only_shelves_sync
        # 1 -> 0: nothing has to be done
        # 0 -> 1: all synced books have to be added to archived books, + currently synced shelfs which
        # don't have to be synced have to be removed (added to Shelf archive)
        current_user.kobo_only_shelves_sync = int(to_save.get("kobo_only_shelves_sync") == "on") or 0
        if old_state == 0 and current_user.kobo_only_shelves_sync == 1:
            kobo_sync_status.update_on_sync_shelfs(current_user.id)

    except Exception as ex:
        flash(str(ex), category="error")
        return render_title_template("user_edit.html",
                                     content=current_user,
                                     config=config,
                                     translations=translations,
                                     profile=1,
                                     languages=languages,
                                     title=_("%(name)s's Profile", name=current_user.name),
                                     page="me",
                                     kobo_support=kobo_support,
                                     registered_oauth=local_oauth_check,
                                     oauth_status=oauth_status)

    val = 0
    for key, __ in to_save.items():
        if key.startswith('show'):
            val += int(key[5:])
    current_user.sidebar_view = val
    if to_save.get("Show_detail_random"):
        current_user.sidebar_view += constants.DETAIL_RANDOM

    try:
        ub.session.commit()
        flash(_("Success! Profile Updated"), category="success")
        log.debug("Profile updated")
    except IntegrityError:
        ub.session.rollback()
        flash(_("Oops! An account already exists for this Email."), category="error")
        log.debug("Found an existing account for this Email")
    except OperationalError as e:
        ub.session.rollback()
        log.error("Database error: %s", e)
        flash(_("Oops! Database Error: %(error)s.", error=e), category="error")


@web.route("/me", methods=["GET", "POST"])
@user_login_required
def profile():
    languages = calibre_db.speaking_language()
    translations = get_available_locale()
    kobo_support = feature_support['kobo'] and config.config_kobo_sync
    if feature_support['oauth'] and config.config_login_type == 2:
        oauth_status = get_oauth_status()
        local_oauth_check = oauth_check
    else:
        oauth_status = None
        local_oauth_check = {}

    if request.method == "POST":
        change_profile(kobo_support, local_oauth_check, oauth_status, translations, languages)
    return render_title_template("user_edit.html",
                                 translations=translations,
                                 profile=1,
                                 languages=languages,
                                 content=current_user,
                                 config=config,
                                 kobo_support=kobo_support,
                                 title=_("%(name)s's Profile", name=current_user.name),
                                 page="me",
                                 registered_oauth=local_oauth_check,
                                 oauth_status=oauth_status)


# ###################################Show single book ##################################################################


@web.route("/read/<int:book_id>/<book_format>")
@login_required_if_no_ano
@viewer_required
def read_book(book_id, book_format):
    book = calibre_db.get_filtered_book(book_id)

    if not book:
        flash(_("Oops! Selected book is unavailable. File does not exist or is not accessible"),
              category="error")
        log.debug("Selected book is unavailable. File does not exist or is not accessible")
        return redirect(url_for("web.index"))

    book.ordered_authors = calibre_db.order_authors([book], False)

    # check if book has a bookmark
    bookmark = None
    if current_user.is_authenticated:
        bookmark = ub.session.query(ub.Bookmark).filter(and_(ub.Bookmark.user_id == int(current_user.id),
                                                             ub.Bookmark.book_id == book_id,
                                                             ub.Bookmark.format == book_format.upper())).first()
    if book_format.lower() == "epub" or book_format.lower() == "kepub":
        log.debug("Start [k]epub reader for %d", book_id)
        return render_title_template('read.html', bookid=book_id, title=book.title, bookmark=bookmark,
                                     book_format=book_format)
    elif book_format.lower() == "pdf":
        log.debug("Start pdf reader for %d", book_id)
        return render_title_template('readpdf.html', pdffile=book_id, title=book.title)
    elif book_format.lower() == "txt":
        log.debug("Start txt reader for %d", book_id)
        return render_title_template('readtxt.html', txtfile=book_id, title=book.title)
    elif book_format.lower() in ["djvu", "djv"]:
        log.debug("Start djvu reader for %d", book_id)
        return render_title_template('readdjvu.html', djvufile=book_id, title=book.title,
                                     extension=book_format.lower())
    else:
        for fileExt in constants.EXTENSIONS_AUDIO:
            if book_format.lower() == fileExt:
                entries = calibre_db.get_filtered_book(book_id)
                log.debug("Start mp3 listening for %d", book_id)
                return render_title_template('listenmp3.html', mp3file=book_id, audioformat=book_format.lower(),
                                             entry=entries, bookmark=bookmark)
        for fileExt in ["cbr", "cbt", "cbz"]:
            if book_format.lower() == fileExt:
                all_name = str(book_id)
                title = book.title
                if len(book.series):
                    title = title + " - " + book.series[0].name
                    if book.series_index:
                        title = title + " #" + '{0:.2f}'.format(book.series_index).rstrip('0').rstrip('.')
                log.debug("Start comic reader for %d", book_id)
                return render_title_template('readcbr.html', comicfile=all_name, title=title,
                                             extension=fileExt, bookmark=bookmark)
        log.debug("Selected book is unavailable. File does not exist or is not accessible")
        flash(_("Oops! Selected book is unavailable. File does not exist or is not accessible"),
              category="error")
        return redirect(url_for("web.index"))


@web.route("/book/<int:book_id>")
@login_required_if_no_ano
def show_book(book_id):
    entries = calibre_db.get_book_read_archived(book_id, config.config_read_column, allow_show_archived=True)
    if entries:
        read_book = entries[1]
        archived_book = entries[2]
        entry = entries[0]
        entry.read_status = read_book == ub.ReadBook.STATUS_FINISHED
        entry.is_archived = archived_book
        for lang_index in range(0, len(entry.languages)):
            entry.languages[lang_index].language_name = isoLanguages.get_language_name(get_locale(), entry.languages[
                lang_index].lang_code)
        cc = calibre_db.get_cc_columns(config, filter_config_custom_read=True)
        book_in_shelves = []
        shelves = ub.session.query(ub.BookShelf).filter(ub.BookShelf.book_id == book_id).all()
        for sh in shelves:
            book_in_shelves.append(sh.shelf)

        entry.tags = sort(entry.tags, key=lambda tag: tag.name)

        entry.ordered_authors = calibre_db.order_authors([entry])

        entry.email_share_list = check_send_to_ereader(entry)
        entry.reader_list = check_read_formats(entry)

        entry.reader_list_sizes = dict()
        for data in entry.data:
            if data.format.lower() in entry.reader_list:
                entry.reader_list_sizes[data.format.lower()] = data.uncompressed_size

        # Fetch User Preferences
        pref_book_status = 0
        pref_author_ids = {}
        pref_series_status = 0
        if current_user.is_authenticated:
            # Book Pref
            book_pref = ub.session.query(ub.UserPreference).filter(
                ub.UserPreference.user_id == current_user.id,
                ub.UserPreference.item_type == constants.ITEM_TYPE_BOOK,
                ub.UserPreference.item_id == book_id
            ).first()
            if book_pref:
                pref_book_status = book_pref.status

            # Author Prefs
            author_ids = [a.id for a in entry.ordered_authors]
            if author_ids:
                author_prefs = ub.session.query(ub.UserPreference).filter(
                    ub.UserPreference.user_id == current_user.id,
                    ub.UserPreference.item_type == constants.ITEM_TYPE_AUTHOR,
                    ub.UserPreference.item_id.in_(author_ids)
                ).all()
                pref_author_ids = {p.item_id: p.status for p in author_prefs}

            # Series Pref
            if entry.series:
                series_id = entry.series[0].id
                series_pref = ub.session.query(ub.UserPreference).filter(
                    ub.UserPreference.user_id == current_user.id,
                    ub.UserPreference.item_type == constants.ITEM_TYPE_SERIES,
                    ub.UserPreference.item_id == series_id
                ).first()
                if series_pref:
                    pref_series_status = series_pref.status

        return render_title_template('detail.html',
                                     entry=entry,
                                     cc=cc,
                                     is_xhr=request.headers.get('X-Requested-With') == 'XMLHttpRequest',
                                     title=entry.title,
                                     books_shelfs=book_in_shelves,
                                     page="book",
                                     pref_book_status=pref_book_status,
                                     pref_author_ids=pref_author_ids,
                                     pref_series_status=pref_series_status,
                                     health=audit_helper.get_book_health(entry, config.get_book_path(), quick=True))
    else:
        log.debug("Selected book is unavailable. File does not exist or is not accessible")
        flash(_("Oops! Selected book is unavailable. File does not exist or is not accessible"),
              category="error")
        return redirect(url_for("web.index"))

# AJAX Endpoints for Hierarchy List View
@web.route("/ajax/author/<int:author_id>/hierarchy")
@login_required_if_no_ano
def get_author_hierarchy(author_id):
    try:
        # Get all visible books for this author
        query = calibre_db.session.query(db.Books).filter(db.Books.authors.any(db.Authors.id == author_id)).filter(calibre_db.common_filters())
        books = query.all()

        series_map = {}
        standalone_books = []

        # Get user preferences for series
        series_prefs = {}
        if current_user.is_authenticated:
            prefs = ub.session.query(ub.UserPreference).filter(
                ub.UserPreference.user_id == current_user.id,
                ub.UserPreference.item_type == constants.ITEM_TYPE_SERIES
            ).all()
            series_prefs = {p.item_id: p.status for p in prefs}

        for book in books:
            if book.series:
                for s in book.series:
                    if s.id not in series_map:
                        series_map[s.id] = {
                            "id": s.id,
                            "name": s.name,
                            "count": 0,
                            "pref_status": series_prefs.get(s.id, 0)
                        }
                    series_map[s.id]["count"] += 1
            else:
                standalone_books.append({
                    "id": book.id,
                    "title": book.title,
                    "has_cover": book.has_cover,
                    "format": [f.format.lower() for f in book.data]
                })

        # Format series list
        series_list = [{
            "id": v["id"],
            "name": v["name"] or _("Unknown Series"),
            "count": v["count"],
            "pref_status": v["pref_status"]
        } for k, v in series_map.items()]
        series_list.sort(key=lambda x: x["name"])
        standalone_books.sort(key=lambda x: x["title"] or "")

        return jsonify({"success": True, "series": series_list, "books": standalone_books})
    except Exception as e:
        log.error(f"Hierarchy Error: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})

@web.route("/ajax/series/<int:series_id>/books")
@login_required_if_no_ano
def get_series_books_ajax(series_id):
    try:
        query = calibre_db.session.query(db.Books).filter(db.Books.series.any(db.Series.id == series_id)).filter(calibre_db.common_filters())
        books = query.all()
        
        books_list = []
        for book in books:
             books_list.append({
                 "id": book.id,
                 "title": book.title,
                 "series_index": book.series_index,
                 "has_cover": book.has_cover,
                 "format": [f.format.lower() for f in book.data]
             })
             
        try:
            books_list.sort(key=lambda x: float(x["series_index"]) if x["series_index"] else 9999)
        except:
             books_list.sort(key=lambda x: x["series_index"])
             
        return jsonify({"success": True, "books": books_list})
    except Exception as e:
        log.error(f"Series Ajax Error: {e}")
        import traceback
        log.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})

