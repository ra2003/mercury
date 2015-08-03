#
# This file should not be edited unless you're a high roller
# or you know what you're doing.
# 

from core.libs.playhouse.sqlite_ext import SqliteExtDatabase, MySQLDatabase

import os, importlib
_sep = os.sep

from .defaults import *

__author__ = 'Serdar Yegulalp'
__version__ = '0.0.1'
__license__ = 'MIT'
__copyright_date__ = "2015"

PRODUCT_NAME = "MeTal " + __version__

# Relative path for static content used by MeTal itself.
# Leave this as-is for most functionality.

DATA_FILE_PATH = _sep + 'data'
EXPORT_FILE_PATH = DATA_FILE_PATH + _sep + 'saved'
PLUGIN_FILE_PATH = DATA_FILE_PATH + _sep + 'plugins'

# Top-level path to the application.
# Automatically calculated; does not need to be changed.

PLUGIN_PATH = APPLICATION_PATH + PLUGIN_FILE_PATH
STATIC_FILE_PATH = APPLICATION_PATH + _sep + 'static'
STATIC_PATH = '/static'

# Database path for Sqlite. Leave this as it is
# unless you want the database in another directory.
SQLITE_FILE_NAME = 'my_database.db'
SQLITE_DATABASE_PATH = DATA_FILE_PATH + _sep + SQLITE_FILE_NAME 
FULL_SQLITE_DATABASE_PATH = APPLICATION_PATH + SQLITE_DATABASE_PATH
DATABASE_PATH = FULL_SQLITE_DATABASE_PATH

from configparser import ConfigParser

config_file = APPLICATION_PATH + os.sep + 'data' + os.sep + INI_FILE_NAME

parser = ConfigParser()
parser.read(config_file)

if len(parser.sections()) == 0:
    NO_SETUP = True
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

try:
    # TODO: http or https?
    BASE_URL_ROOT = "http://" + os.environ["HTTP_HOST"]
    BASE_URL_PATH = DEFAULT_URL_PATH
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

    BASE_URL_ROOT = "http://" + DEFAULT_LOCAL_ADDRESS + DEFAULT_LOCAL_PORT
    BASE_URL = BASE_URL_ROOT + BASE_PATH
    
    USE_WSGI = False
else:
    BASE_PATH = ""
    BASE_URL = BASE_URL_ROOT + BASE_URL_PATH
    
try:
    DB_TYPE_NAME
except:
    DB_TYPE_NAME = 'sqlite'
    
# get the matching module from core.models.db (move it around to avoid name collisions)
# put these functions in those modules
# better than this clumsy multi-if and more flexible

#db_module = importlib.import_module("core.models." + DB_TYPE_NAME)
#DB = db_module
#DB_TYPE = DB.db_type()

if DB_TYPE_NAME == 'sqlite':
    DB_TYPE = SqliteExtDatabase(
        FULL_SQLITE_DATABASE_PATH,
        threadlocals=True,
        timeout=DATABASE_TIMEOUT)
    from core.models import sqlite
    DB = sqlite    

if DB_TYPE_NAME == 'mysql':
    DB_TYPE = MySQLDatabase(DB_ID, user=DB_USER, passwd=DB_PASSWORD)
    from core.models import mysql
    DB = mysql
