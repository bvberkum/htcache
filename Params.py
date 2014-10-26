import os, re, socket, sys



### Constants

VERSION = 0.4

# defaults
QUIET = False
LOG_LEVEL = 7 # 
ERROR_LEVEL = LOG_LEVEL
DEBUG = []
DEBUG_BE = False
DEBUG_FIBER = False
#LOG_FACILITIES = []
#MAIN_LOG = os.getenv('MAIN_LOG') or 'main.log'
#MAIN_LOG
#LOG_MODULE_ARGS = 7, 'main.log'

LOG = None
ONLINE = True
LIMIT = False
TIMEOUT = 15
STATIC = False
FAMILY = socket.AF_INET
PORT = 8080
HOSTNAME = socket.gethostname()

ROOT = os.getcwd() + os.sep
DATA_DIR = '/var/lib/htcache/'
DATA = 'sqlite:///'+DATA_DIR+'resources.sql'
LOG_DIR = '/var/log/htcache/'
PID_FILE = '/var/run/htcache.pid'
CACHE = 'caches.FileTree'
ARCHIVE = ''
NODIR = False
ENCODE_PATHSEP = ''

DROP_FILE = '/etc/htcache/rules.drop'
JOIN_FILE = '/etc/htcache/rules.join'
NOCACHE_FILE = '/etc/htcache/rules.nocache'
REWRITE_FILE = '/etc/htcache/rules.rewrite'

PROXY_INJECT = False
PARTIAL = '.incomplete'
DEFAULT = 'default'

# XXX non user-configurable
MAX_PATH_LENGTH = 256
MAXCHUNK = 1448 # maximum lan packet?
TIMEFMT = '%a, %d %b %Y %H:%M:%S GMT'
ALTTIMEFMT = '%a, %d %b %H:%M:%S CEST %Y' # XXX: foksuk.nl
IMG_TYPE_EXT = 'png','jpg','gif','jpeg','jpe'
HTML_PLACEHOLDER = DATA_DIR+'filtered-placeholder.html'
IMG_PLACEHOLDER = DATA_DIR+'forbidden-sign.png'
PROXY_INJECT_JS = DATA_DIR+'dhtml.js'
PROXY_INJECT_CSS = DATA_DIR+'dhtml.css'

