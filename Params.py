import os, re, socket, sys



### Constants

VERSION = 0.4

LOG_EMERG, \
LOG_ALERT, \
LOG_CRIT, \
LOG_ERR, \
LOG_WARN, \
LOG_NOTE, \
LOG_INFO, \
LOG_DEBUG = range(0, 8)


# defaults
ONLINE = True
DEBUG = False
LIMIT = False
LOG = False
TIMEOUT = 15
STATIC = False
FAMILY = socket.AF_INET
PORT = 8080
HOSTNAME = socket.gethostname()
ROOT = os.getcwd() + os.sep
DATA_DIR = '/var/lib/htcache/'
DATA = 'sqlite://'+DATA_DIR+'resources.sql'

PID_FILE = '/var/run/htcache.pid'
CACHE = 'caches.FileTree'
ARCHIVE = ''
NODIR = False
ENCODE_PATHSEP = ''

QUIET = False
VERBOSE = 3 # error

DROP_FILE = '/etc/htcache/rules.drop'
JOIN_FILE = '/etc/htcache/rules.join'
NOCACHE_FILE = '/etc/htcache/rules.nocache'
REWRITE_FILE = '/etc/htcache/rules.rewrite'

PROXY_INJECT = False
PARTIAL = '.incomplete'

# non user-configurable
MAX_PATH_LENGTH = 256
MAXCHUNK = 1448 # maximum lan packet?
TIMEFMT = '%a, %d %b %Y %H:%M:%S GMT'
ALTTIMEFMT = '%a, %d %b %H:%M:%S CEST %Y' # XXX: foksuk.nl
IMG_TYPE_EXT = 'png','jpg','gif','jpeg','jpe'
HTML_PLACEHOLDER = DATA_DIR+'filtered-placeholder.html'
IMG_PLACEHOLDER = DATA_DIR+'forbidden-sign.png'
PROXY_INJECT_JS = DATA_DIR+'dhtml.js'
PROXY_INJECT_CSS = DATA_DIR+'dhtml.css'

