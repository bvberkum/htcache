import os, re, socket, sys
# XXX: Dont use cjson, its buggy, see comments at
# http://pypi.python.org/pypi/python-cjson
# use jsonlib or simplejson
try:
    import simplejson as _json
except:
    import json as _json

json_read = _json.loads
json_write = _json.dumps

_args = iter( sys.argv )

VERSION = 0.4

# proxy params
PROG = _args.next()
PORT = 8080
ROOT = os.getcwd() + os.sep
PID_FILE = '/var/run/htcache.pid'
VERBOSE = 0
TIMEOUT = 15
FAMILY = socket.AF_INET
STATIC = False
ONLINE = True # XXX:bvb: useless..
LIMIT = False
LOG = False
DEBUG = False
DROP = []
DROP_FILE = '/etc/htcache/rules.drop'
JOIN = []
JOIN_FILE = '/etc/htcache/rules.join'
NOCACHE = []
NOCACHE_FILE = '/etc/htcache/rules.nocache'
REWRITE = []
REWRITE_FILE = '/etc/htcache/rules.rewrite'
CACHE = 'caches.FileTree'
ARCHIVE = ''
ENCODE_PATHSEP = ''
FileTreeQ_SORT = True
FileTreeQ_ENCODE = False
# non user-configurable
MAX_PATH_LENGTH = 256
MAXCHUNK = 1448 # maximum lan packet?
TIMEFMT = '%a, %d %b %Y %H:%M:%S GMT'
ALTTIMEFMT = '%a, %d %b %H:%M:%S CEST %Y' # foksuk.nl
PARTIAL = '.incomplete'
IMG_TYPE_EXT = 'png','jpg','gif','jpeg','jpe'
DATA_DIR = '/var/lib/htcache/'
RESOURCES = DATA_DIR+'resource.db'
HTML_PLACEHOLDER = DATA_DIR+'filtered-placeholder.html'
IMG_PLACEHOLDER = DATA_DIR+'forbidden-sign.png'
PROXY_INJECT_JS = DATA_DIR+'htcache.js'
# query params
PRINT_RECORD = []
PRINT_ALLRECORDS = False
PRINT_MEDIA = []
FIND_RECORDS = {}

USAGE = '''usage: %(PROG)s [options]

  -h --help          show this help message and exit

Proxy:
  -p --port PORT     listen on this port for incoming connections, default %(PORT)i
  -r --root DIR      set cache root directory, default current: %(ROOT)s
     --static        static mode; assume files never change
     --offline       offline mode; never connect to server
     --limit RATE    FIXME: limit download rate at a fixed K/s
     --daemon LOG    daemonize process and print PID, route output to LOG
     --debug         switch from gather to debug output module

Cache:
  -f RESOURCES

Rules:
  -d --drop FILE     filter requests for URI's based on regex patterns.
                     read line for line from file, default %(DROP_FILE)s.
  -n --nocache FILE  TODO: bypass caching for requests based on regex pattern.

Misc.:
  -t --timeout SEC   break connection after so many seconds of inactivity,
                     default %(TIMEOUT)i
  -6 --ipv6          try ipv6 addresses if available
  -v --verbose       increase output, use twice to show http headers
                    ''' % locals()


for _arg in _args:

    if _arg in ( '-h', '--help' ):
        sys.exit( USAGE )
    elif _arg in ( '-p', '--port' ):
        try:
            PORT = int( _args.next() )
            assert PORT > 0
        except:
            sys.exit( 'Error: %s requires a positive numerical argument' % _arg )
    elif _arg in ( '-d', '--drop' ):
        try:
            DROP_FILE = os.path.realpath(_args.next())
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )
    elif _arg in ( '-n', '--nocache' ):
        try:
            NOCACHE_FILE = os.path.realpath(_args.next())
            #assert os.path.exists(NOCACHE_FILE)
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )
    elif _arg in ( '-r', '--root' ):
        try:
            ROOT = os.path.realpath( _args.next() ) + os.sep
            assert os.path.isdir( ROOT )
        except StopIteration:
            sys.exit( 'Error: %s requires a directory argument' % _arg )
        except:
            sys.exit( 'Error: invalid cache directory %s' % ROOT )
    elif _arg in ( '-v', '--verbose' ):
        VERBOSE += 1
    elif _arg in ( '--nodir' ):
        pass # XXX
        #try:
        _args.next()
        #except:
        #    sys.exit( 'Error: %s requires argument' % _arg )
    elif _arg in ( '--cache' ):
        try:
            CACHE = _args.next()
        except:
            sys.exit( 'Error: %s requires argument' % _arg )
    elif _arg in ( '-t', '--timeout' ):
        try:
            TIMEOUT = int( _args.next() )
            assert TIMEOUT > 0
        except:
            sys.exit( 'Error: %s requires a positive numerical argument' % _arg )
    elif _arg in ( '-6', '--ipv6' ):
        FAMILY = socket.AF_UNSPEC
    elif _arg == '--static':
        STATIC = True
    elif _arg == '--daemon':
        LOG = _args.next()
    elif _arg == '--debug':
        DEBUG = True
    elif _arg == '-f':
        RESOURCES = _args.next()
    elif _arg in ('--pid-file',):
        PID_FILE = _args.next()

    else:
        sys.exit( 'Error: invalid option %r' % _arg )


def log(msg, threshold=0):
  "Not much of a log.."
  # see fiber.py which manages stdio
  if VERBOSE > threshold:
    print msg

def parse_droplist(fpath=DROP_FILE):
    global DROP
    DROP = []
    if os.path.isfile(fpath):
        DROP.extend([(p.strip(), re.compile(p.strip())) for p in
            open(fpath).readlines() if p.strip() and not p.startswith('#')])

def parse_nocache(fpath=NOCACHE_FILE):
    global NOCACHE
    NOCACHE = []
    if os.path.isfile(fpath):
        NOCACHE.extend([(p.strip(), re.compile(p.strip())) for p in
            open(fpath).readlines() if p.strip() and not p.startswith('#')])


def parse_joinlist(fpath=JOIN_FILE):
    global JOIN
    JOIN = []
    if os.path.isfile(fpath):
        JOIN.extend([(p.strip(), re.compile(p.split(' ')[0].strip())) for p in
            open(fpath).readlines() if p.strip() and not p.strip().startswith('#')])

def parse_rewritelist(fpath=REWRITE_FILE):
    global REWRITE_FILE
    REWRITE = []
    if os.path.isfile(fpath):
        REWRITE.extend([(p.strip(), re.compile(p.split(' ')[0].strip())) for p in
            open(fpath).readlines() if p.strip() and not p.strip().startswith('#')])


def validate_joinlist(fpath=JOIN_FILE):
    lines = [path[2:].strip() for path in open(fpath).readlines() if path.strip() and path.strip()[1]=='#']
    for path in lines:
        match = False
        for line, regex in JOIN:
            m = regex.match(line)
            if m:
                print 'Match', path, m.groups()
                match = True
        if not match:
            print "Error: no match for", path

def format_info():
    """
    Return JSON for config.
    """
    return json_write({
        "htache": { 
            "runtime": {
                "program": PROG,
            },
            "config": {
                "port": PORT,
                "root": ROOT,
                "pid-file": PID_FILE,
                "verboseness": VERBOSE,
                "timeout": TIMEOUT,
                "socket-family": FAMILY,
                "cache-type": CACHE,
                "join-file": JOIN_FILE,
                "drop-file": DROP_FILE,
                "nocache-file": NOCACHE_FILE,
                "rewrite-file": REWRITE_FILE,
            },
            "statistics": {
                "rules": {
                        "drop": len(DROP),
                        "join": len(JOIN),
                        "nocache": len(NOCACHE),
                        "rewrite": len(REWRITE),
                    }
                }
            }
        })


if __name__ == '__main__':
	parse_joinlist()
	validate_joinlist()
