#
# This file should not be edited unless you're a high roller
# or you know what you're doing.
#

import os  # , importlib
# _sep = os.sep
from os.path import join as _join

from .defaults import *

__author__ = 'Serdar Yegulalp'
__version__ = '0.0.1'
__license__ = 'MIT'
__copyright_date__ = "2016"

PRODUCT_NAME = "Mercury " + __version__

# Relative path for static content used by Mercury itself.
# Leave this as-is for most functionality.

# DATA_FILE_PATH = _join('', 'data')
DATA_FILE_PATH = os.sep + 'data'
# EXPORT_FILE_PATH = DATA_FILE_PATH + _sep + 'saved'
EXPORT_FILE_PATH = _join(DATA_FILE_PATH, 'saved')
# PLUGIN_FILE_PATH = DATA_FILE_PATH + _sep + 'plugins'
PLUGIN_FILE_PATH = _join(DATA_FILE_PATH, 'plugins')

# Top-level path to the application.
# Automatically calculated; does not need to be changed.

PLUGIN_PATH = APPLICATION_PATH + PLUGIN_FILE_PATH
STATIC_FILE_PATH = _join(APPLICATION_PATH, 'static')
THEME_FILE_PATH = _join(APPLICATION_PATH + DATA_FILE_PATH, 'themes')
STATIC_PATH = '/static'

# Database path for Sqlite. Leave this as it is
# unless you want the database in another directory.
SQLITE_FILE_NAME = 'database.cgi'
SQLITE_DATABASE_PATH = _join(DATA_FILE_PATH, SQLITE_FILE_NAME)
FULL_SQLITE_DATABASE_PATH = APPLICATION_PATH + SQLITE_DATABASE_PATH
DATABASE_PATH = FULL_SQLITE_DATABASE_PATH
NO_SETUP = False

from configparser import ConfigParser

config_file = _join(APPLICATION_PATH, 'data', INI_FILE_NAME)

parser = ConfigParser()
parser.read(config_file)

# where to get the protocol from?

if len(parser.sections()) == 0:
    NO_SETUP = True
    try:
        BASE_URL_NETLOC = os.environ["HTTP_HOST"]
        BASE_URL_ROOT = BASE_URL_PROTOCOL + BASE_URL_NETLOC
        BASE_URL_PATH = os.environ["REQUEST_URI"]
    except KeyError:
        pass

else:
    NO_SETUP = False

    for items in parser.sections():
        for name, value in parser.items(items):
            option = name.upper()
            if value in ('True', 'False', 'None'):
                locals()[option] = parser.getboolean(items, option)
            else:
                locals()[option] = value

if INSTALL_STEP is not None:
    NO_SETUP = True

# TODO: this needs to be scrapped and rewritten to use WSGI properly
# by way of FastCGI or what have you
# we need to set the mode explicitly somewhere

# APP_MODE = 'cgi','fastcgi','auto'

# just get rid of desktop mode entirely


'''
try:
    DEFAULT_LOCAL_ADDRESS = os.environ["HTTP_HOST"]
except KeyError:
    # TODO: what if this throws a false positive
    # if we're simply running as a server?
    DESKTOP_MODE = True

if DESKTOP_MODE is True:
    if NO_SETUP is True:
        BASE_PATH = ""
        BASE_URL = DEFAULT_LOCAL_ADDRESS
        BASE_URL_PATH = ""
    else:
        BASE_PATH = "/~"

    BASE_URL_ROOT = BASE_URL_PROTOCOL + DEFAULT_LOCAL_ADDRESS + DEFAULT_LOCAL_PORT
    BASE_URL = BASE_URL_ROOT + BASE_PATH

    USE_WSGI = False
else:

    BASE_PATH = ""
    BASE_URL_ROOT = BASE_URL_PROTOCOL + BASE_URL_NETLOC
    BASE_URL = BASE_URL_ROOT + BASE_URL_PATH
'''
SERVER_MODE = 'cgi'

BASE_PATH = ""
BASE_URL_ROOT = BASE_URL_PROTOCOL + BASE_URL_NETLOC
BASE_URL = BASE_URL_ROOT + BASE_URL_PATH

try:
    DB_TYPE_NAME
except:
    DB_TYPE_NAME = 'sqlite'

if DB_TYPE_NAME == 'sqlite':
    from core.libs.playhouse.sqlite_ext import SqliteExtDatabase

    class SqliteDB(SqliteExtDatabase):
        def initialize_connection(self, conn=None):
            pass

    DB_TYPE = SqliteDB(
        FULL_SQLITE_DATABASE_PATH,
        threadlocals=True,
        timeout=30000
        )


    DB_TYPE.initialize_connection()

    from core.models import sqlite as DB

#     # eventually it'll look like this....
#
#     from core.models.db import sqlite
#
#     DB = sqlite.SqliteDB(
#         FULL_SQLITE_DATABASE_PATH,
#         threadlocals=True,
#         timeout=30000
#         )
#
#     DB.initialize_connection()
#
#     DB_TYPE = DB


# elif DB_TYPE_NAME == 'mysql':
#     from core.libs.playhouse.sqlite_ext import MySQLDatabase
#     DB_TYPE = MySQLDatabase(DB_ID, user=DB_USER, passwd=DB_PASSWORD)
#     from core.models import mysql as DB