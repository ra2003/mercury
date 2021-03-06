import urllib, re, html, hashlib, base64

from settings import (MAX_BASENAME_LENGTH, ITEMS_PER_PAGE,
    PASSWORD_KEY, SECRET_KEY, BASE_URL, APPLICATION_PATH,
    EXPORT_FILE_PATH)

from core.libs.bottle import redirect, response, _stderr

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def reboot():
    import os, signal
    os.kill(os.getpid(), signal.SIGTERM)


def default(obj):
    import datetime
    if isinstance(obj, datetime.datetime):
        return datetime.datetime.strftime(obj, DATE_FORMAT)


def json_dump(obj):
    import json
    from core.libs.playhouse.shortcuts import model_to_dict
    # we have to do this as a way to keep dates from choking
    return json.loads(json.dumps(model_to_dict(obj, recurse=False),
            default=default,
            separators=(', ', ': '),
            indent=1))

# TODO: move this out of here and into a more appropriate place
# also, use a proper exception catching mechanism!


def field_error(e):
    _ = re.compile('UNIQUE constraint failed: (.*)$')
    m = _.match(str(e))
    error = {'blog.local_path':'''
The file path for this blog is the same as another blog in this system.
File paths must be unique.
''', 'blog.url':'''
The URL for this blog is the same as another blog in this system.
URLs for blogs must be unique.
'''}[m.group(1)]
    return error


def xml_escape(string):
    string = string.replace("&", "&amp;")
    return string


def quote_escape(string):
    string = string.replace("'", "&#39")
    string = string.replace('"', "&#34")
    return string


def preview_file(identifier, extension):
    import zlib
    filename = "{}.preview-{}.{}".format(
        identifier,
        str(zlib.crc32(identifier.encode('utf-8'), 0xFFFF)),
        extension
        )
    return filename


def verify_path(path):
    '''
    Stub function to ensure a given path
    a) exists (create if not)
    b) is writable
    c) is not on top of a path used by the application
    '''

    # verify the path exists
    # verify that it is writable
    # verify it is not within the application directory
    # os.path.abspath may help here

    pass


def is_blank(string):
    if string is None:
        return True
    if len(string) == 0:
        return True
    if string and string.strip():
        return False
    return True


def url_escape(url):
    return urllib.parse.quote_plus(url)


def url_unescape(url):
    return urllib.parse.unquote_plus(url)


def safe_redirect(url):
    url_unquoted = urllib.parse.unquote_plus(url)
    if url_unquoted.startswith(BASE_URL + "/"):
        redirect(url)
    else:
        redirect(BASE_URL)


def _stddebug_():
    from core.boot import settings
    _stddebug = lambda x: _stderr(x) if (settings.DEBUG_MODE is True) else lambda x: None  # @UnusedVariable
    return _stddebug


class Status:
    '''
    Used to create status messages for AJAX UI.
    '''
    status_types = {'success':'ok-sign',
        'info':'info-sign',
        'warning':'exclamation-sign',
        'danger':'remove-sign'}

    def __init__(self, **ka):

        self.type = ka['type']
        if 'vals' in ka:
            formatting = list(map(html_escape, ka['vals']))
            self.message = ka['message'].format(*formatting)
        else:
            self.message = ka['message']

        if self.type not in ('success', 'info') and 'no_sure' not in ka:
            self.message += "<p><b>Are you sure you want to do this?</b></p>"

        if self.type in self.status_types:
            self.icon = self.status_types[self.type]

        self.confirm = ka.get('yes', None)
        self.deny = ka.get('no', None)

        self.action = ka.get('action', None)
        self.url = ka.get('url', None)

        self.message_list = ka.get('message_list', None)
        self.close = ka.get('close', True)


def logout_nonce(user):
    return csrf_hash(str(user.id) + str(user.last_login) + 'LOGOUT')


def csrf_hash(csrf):
    '''
    Generates a CSRF token value, by taking an input and generating a SHA-256 hash from it,
    in conjunction with the secret key set for the installation.
    '''

    enc = str(csrf) + SECRET_KEY

    m = hashlib.sha256()
    m.update(enc.encode('utf-8'))
    m = m.digest()
    encrypted_csrf = base64.b64encode(m).decode('utf-8')

    return (encrypted_csrf)


def csrf_tag(csrf):
    '''
    Generates a hidden input field used to carry the CSRF token for form submissions.
    '''
    return "<input type='hidden' name='csrf' id='csrf' value='{}'>".format(csrf_hash(csrf))


def string_to_date(date_string):
    import datetime
    return datetime.datetime.strptime(date_string, DATE_FORMAT)


def date_format(date_time):
    '''
    Formats a datetime value in a consistent way for presentation.
    '%Y-%m-%d %H:%M:%S' is the standard format.
    '''
    if date_time is None:
        return ''
    else:
        return date_time.strftime(DATE_FORMAT)


def utf8_escape(input_string):
    '''
    Used for cross-converting a string to encoded UTF8;
    for instance, for database submissions,
    '''
    return bytes(input_string, 'iso-8859-1').decode('utf-8')


def html_escape(input_string, quote=True):
    '''
    Used for returning text from the server that might have HTML that needs escaping,
    such as a status message that might have spurious HTML in it (e.g., a page title).
    '''
    return html.escape(str(input_string), quote)

# http://stackoverflow.com/a/517974


def remove_accents(input_str):
    import unicodedata
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def create_basename_core(basename):

    basename = remove_accents(basename)

    try:
        basename = basename.casefold()
    except Exception:
        basename = basename.lower()

    basename = re.sub(r'[ \./]', r'-', basename)
    basename = re.sub(r'<[^>]*>', r'', basename)
    basename = re.sub(r'[^a-z0-9\-]*', r'', basename)
    basename = re.sub(r'\-\-', r'-', basename)

    basename = urllib.parse.quote_plus(basename)

    return basename


def create_basename(input_string, blog):
    '''
    Generate a basename from a given input string.

    Checks across the entire blog in question for a basename collision.

    Basenames need to be unique to the filesystem for where the target files
    are to be written. By default this is enforced in the database by way of a
    unique column constraint.
    '''

    if not input_string:
        input_string = "page"

    basename = input_string
    basename_test = create_basename_core(basename)

    from core.models import Page

    n = 0

    while True:

        try:
            Page.get(Page.basename == basename_test,
                Page.blog == blog)
        except Page.DoesNotExist:
            return (basename_test[:MAX_BASENAME_LENGTH])

        n += 1
        basename_test = basename + "-" + str(n)


def trunc(string, length=128):
    '''
    Truncates a string with ellipses.
    This function may eventually be replaced with a CSS-based approach.
    '''
    if string is None:
        return ""
    string = (string[:length] + ' ...') if len(string) > length else string
    return string


breaks_list = ['/', '.', '-', '_']


def breaks(string):
    '''
    Used to break up URLs and basenames so they wrap properly
    '''
    if string is None:
        return string

    for n in breaks_list:
        string = string.replace(n, n + '<wbr>')

    return string


def generate_paginator(obj, request, items_per_page=ITEMS_PER_PAGE):

    '''
    Generates a paginator block for browsing lists, for instance in the blog or site view.
    '''

    page_num = page_list_id(request)

    paginator = {}

    paginator['page_count'] = obj.count()

    paginator['max_pages'] = int((paginator['page_count'] / items_per_page) + (paginator['page_count'] % items_per_page > 0))

    page_num = min(page_num, paginator['max_pages'])

    paginator['next_page'] = (page_num + 1) if page_num < paginator['max_pages'] else paginator['max_pages']
    paginator['prev_page'] = (page_num - 1) if page_num > 1 else 1

    paginator['first_item'] = (page_num * items_per_page) - (items_per_page - 1)
    paginator['last_item'] = paginator['page_count'] if (page_num * items_per_page) > paginator['page_count'] else (page_num * items_per_page)

    paginator['page_num'] = page_num
    paginator['items_per_page'] = items_per_page

    # obj_list = obj.naive().paginate(page_num, items_per_page)
    obj_list = obj.paginate(page_num, items_per_page)

    return paginator, obj_list


def generate_date_mapping(date_value, tags, path_string, do_eval=True):
    '''
    Generates a date mapping string, usually from a template mapping,
    using a date value, a tag set, and the supplied path string.
    This is often used for resolving template mappings.
    The tag set is contextual -- e.g., for a blog or a site.
    '''

    if do_eval:
        time_string = eval(path_string, tags.__dict__)
    else:
        time_string = path_string

    if time_string == '' or time_string is None:
        return None

    path_string = date_value.strftime(time_string)

    return path_string


def encrypt_password(password, key=None):

    if key is None:
        p_key = PASSWORD_KEY
    else:
        p_key = key

    bin_password = password.encode('utf-8')
    bin_salt = p_key.encode('utf-8')

    m = hashlib.sha256()
    for n in range(1, 1000):
        m.update(bin_password + bin_salt)
    m = m.digest()
    encrypted_password = base64.b64encode(m)

    return encrypted_password


def memoize(f):
    '''
    Memoization decorator for a function taking one or more arguments.
    '''

    # pinched from http://code.activestate.com/recipes/578231-probably-the-fastest-memoization-decorator-in-the-/
    class memodict(dict):

        def __getitem__(self, *key):
            return dict.__getitem__(self, key)

        def __missing__(self, key):
            ret = self[key] = f(*key)
            return ret

    return memodict().__getitem__


def memoize_delete(obj, item):
    obj.__self__.__delitem__(item)


def _iter(item):
    try:
        (x for x in item)
    except BaseException:
        return (item,)
    else:
        return item


def page_list_id(request):

    if not request.query.page:
        return 1
    try:
        page = int(request.query.page)
    except ValueError:
        return 1
    return page


def raise_request_limit():
    from core.libs import bottle
    import settings
    bottle.BaseRequest.MEMFILE_MAX = settings.MAX_REQUEST


def disable_protection():
    response.set_header('Frame-Options', '')
    # response.set_header('Content-Security-Policy', '')


def action_button(label, url):
    action = "<a href='{}'><button type='button' class='btn btn-xs'>{}</button></a>".format(
        url,
        label
        )

    return action


# from settings import (APPLICATION_PATH, EXPORT_FILE_PATH, DB)
from core.libs.playhouse.dataset import DataSet
import os


def _write(string):
    with open('static/output.html', 'a') as f:
        f.write(string)

# write to
# to fetch: http://www.ioncannon.net/programming/1506/range-requests-with-ajax/


def export_data():
    from settings import DB
    n = ("Beginning export process... Writing files to {}.".format(APPLICATION_PATH + EXPORT_FILE_PATH))
    yield ("<p>" + n)
    _write ("<p>" + n)
    xdb = DataSet(DB.dataset_connection())
    if os.path.isdir(APPLICATION_PATH + EXPORT_FILE_PATH) is False:
        os.makedirs(APPLICATION_PATH + EXPORT_FILE_PATH)
    with xdb.transaction():
        for table_name in xdb.tables:
            if not table_name.startswith("page_search"):
                table = xdb[table_name]
                n = "Exporting table: " + table_name
                yield ("<p>" + n)
                _write ('<p>' + n)
                filename = APPLICATION_PATH + EXPORT_FILE_PATH + '/dump-' + table_name + '.json'
                table.freeze(format='json', filename=filename)
    xdb.close()
    n = "Export process ended. <a href='{}'>Click here to continue.</a>".format(BASE_URL)
    yield ("<p>" + n)
    _write ("<p>" + n)

    # TODO: export n rows at a time from each table into a separate file
    # to make the import process more granular
    # by way of a query:
    # peewee_users = db['user'].find(favorite_orm='peewee')
    # db.freeze(peewee_users, format='json', filename='peewee_users.json')


def import_data():
    from settings import DB
    n = []
    n.append("Beginning import process.")
    # yield "<p>" + n

    n.append("Cleaning DB.")
    # yield "<p>" + n
    try:
        DB.clean_database()
    except:
        from core.models import init_db
        init_db.recreate_database()
        DB.remove_indexes()

    n.append("Clearing tables.")
    # yield "<p>" + n

    xdb = DataSet(DB.dataset_connection())

    # with xdb.atomic() as txn:
    try:
        with xdb.transaction():
            for table_name in xdb.tables:
                n.append("Loading table " + table_name)
                # yield "<p>" + n
                try:
                    table = xdb[table_name]
                except:
                    n.append("<p>Sorry, couldn't create table ", table_name)
                else:
                    filename = (APPLICATION_PATH + EXPORT_FILE_PATH +
                        '/dump-' + table_name + '.json')
                    if os.path.exists(filename):
                        try:
                            table.thaw(format='json',
                                filename=filename,
                                strict=True)
                        except Exception as e:
                            n.append("<p>Sorry, error:{}".format(e))

                    else:
                        n.append("No data for table " + table_name)
                        # yield "<p>" + n
    except Exception as e:
        n.append('Ooops: {}'.e)
    else:
        xdb.query(DB.post_import())
        xdb.close()
        DB.recreate_indexes()
        n.append("Import process ended. <a href='{}'>Click here to continue.</a>".format(BASE_URL))
    return '<p>'.join(n)


def fprint(x):
    raise Exception(x)
