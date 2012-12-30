import os
import socket


DOWNLOADS = None

ONLINE = None
LIMIT = None
PORT = None
HOSTNAME = None
ROOT = None
PID_FILE = None
VERBOSE = None
TIMEOUT = None
STATIC = None
FAMILY = None
# proxy rule files
DROP_FILE = None
JOIN_FILE = None
NOCACHE_FILE = None
REWRITE_FILE = None
DATA_DIR = None
CACHE = 'caches.FileTree'
ARCHIVE = ''
ENCODE_PATHSEP = ''
FileTreeQ_SORT = True
FileTreeQ_ENCODE = False

# misc. program params
LOG = False
DEBUG = False
PRUNE = None

MAX_SIZE_PRUNE = 11*(1024**2)
INTERACTIVE = False

COMMANDS = {}
