import sys, os, socket

_args = iter( sys.argv )

loggers = {}

PROG = _args.next()
QUIET = False
LOG_LEVEL = 0 # 
PORT = 8080
HOSTNAME = socket.gethostname()

ROOT = os.getcwd() + os.sep
LOG_DIR = '/var/log/htcache/'
PID_FILE = '/var/run/htcache.pid'
VERBOSE = 1 # XXX remove, replace..
TIMEOUT = 15
FAMILY = socket.AF_INET
FLAT = False
STATIC = False
ONLINE = True
LIMIT = 0.0
LOG = False
DEBUG = False

PARTIAL = '.incomplete'
DEFAULT = 'default'

MAXCHUNK = 1448 # maximum lan packet?
TIMEFMT = '%a, %d %b %Y %H:%M:%S GMT'
SUFFIX = '.incomplete'
SCRAP = '/etc/http-replicator/scrap.patterns'


#	elif _arg == '--flat':
#		FLAT = True
