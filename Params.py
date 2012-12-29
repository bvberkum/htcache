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



### Main: determine runtime config from constants and ARGV

_args = list( sys.argv )

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

## Variable settings

# proxy params
HOSTNAME = socket.gethostname()
PROG = _args.pop(0)
PORT = 8080
ROOT = os.getcwd() + os.sep
PID_FILE = '/var/run/htcache.pid'
VERBOSE = 3 # error
TIMEOUT = 15
FAMILY = socket.AF_INET
STATIC = False
ONLINE = True # XXX:bvb: useless..
LIMIT = False # XXX unused

# misc. program params
LOG = False
DEBUG = False

# proxy rule files
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
HTML_PLACEHOLDER = DATA_DIR+'filtered-placeholder.html'
IMG_PLACEHOLDER = DATA_DIR+'forbidden-sign.png'
PROXY_INJECT = False
PROXY_INJECT_JS = DATA_DIR+'dhtml.js'
PROXY_INJECT_CSS = DATA_DIR+'dhtml.css'
# Static mode, query params
CMDS = {}

PRUNE = False
MAX_SIZE_PRUNE = 11*(1024**2)
INTERACTIVE = False

USAGE = '''usage: %(PROG)s [options]

  -h --help          show this help message and exit

Proxy:
  -p --port PORT     listen on this port for incoming connections, default %(PORT)i
     --static        static mode; assume files never change
     --offline       offline mode; never connect to server
     --limit RATE    TODO: limit download rate at a fixed K/s
     --daemon LOG    daemonize process and print PID, route output to LOG
     --debug         switch from gather to debug output module

Cache:
  -r --root DIR      set cache root directory, default current: %(ROOT)s
  -c --cache TYPE    use module for caching, default %(CACHE)s.
  XXX: -b --backend REF   initialize metadata backend from reference,
     --data-dir DIR
                     Change location of var datafiles. Note: cannot change
                     location of built-in files, only of storages.

Rules:
     --drop FILE     filter requests for URI's based on regex patterns.
                     read line for line from file, default %(DROP_FILE)s.
     --nocache FILE  TODO: bypass caching for requests based on regex pattern.
     --rewrite FILE  Filter any webresource by selecting on URL or

Query
     --media-image

Misc.:
     --check-refs    TODO: iterate cache references.
     --check-sortlist
                     TODO: iterate cache references,
  -t --timeout SEC   break connection after so many seconds of inactivity,
                     default %(TIMEOUT)i
  -6 --ipv6          try ipv6 addresses if available
  -v --verbose       increase output, use twice to show http headers


See the documentation in ReadMe regarding configuration of the proxy. The
following options don't run the proxy but access the cache and descriptor backend::


Resources:
     --list-locations
     --list-resources
     --print-resources URL[,URL]
                     Print all fields for each record; tab separated, one per line.
     --print-all-records
                     Print the record of all cache locations.
     TODO --find-record KEY:[KEY:]ARG[,...]
                     Search for exact record matches.
     TODO --print-mode line|tree
     TODO --print-url
     TODO --print-path
                     List either URLs or PATHs only, omit record data.
     TODO --print-documents
     TODO --print-videos
     TODO --print-audio
     TODO --print-images
                     Search through predefined list of content-types.

Maintenance:
     --check-
     --prune-gone
                    TODO: Remove resources no longer online.
     --prune-stale
                    Delete outdated cached resources, ie. those that are
                    expired. Also drops records for missing files.
     --link-dupes
                    TODO: Symlink duplicate content, check by size and hash.
                    Requires up to date hash index.
''' % locals()


while _args:
    _arg = _args.pop(0)

    if _arg in ( '-h', '--help' ):
        sys.exit( USAGE )

    elif _arg in ( '-p', '--port' ):
        try:
            PORT = int( _args.pop(0) )
            assert PORT > 0
        except:
            sys.exit( 'Error: %s requires a positive numerical argument' % _arg )

    elif _arg in ( '-c', '--cache' ):
        try:
            CACHE = _args.pop(0)
        except:
            sys.exit( 'Error: %s requires an cache type argument' % _arg )

    elif _arg in ( '--drop', ):
        try:
            DROP_FILE = os.path.realpath(_args.pop(0))
            assert os.path.exists(DROP_FILE)
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )

    elif _arg in ( '--nocache', ):
        try:
            NOCACHE_FILE = os.path.realpath(_args.pop(0))
            assert os.path.exists(NOCACHE_FILE)
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )
    elif _arg in ( '-H', '--hash' ):
        try:
            ROOT = os.path.realpath( _args.pop(0) ) + os.sep
            assert os.path.isdir( ROOT )
        except StopIteration:
            sys.exit( 'Error: %s requires a directory argument' % _arg )
        except:
            sys.exit( 'Error: invalid sha1sum directory %s' % ROOT )

    elif _arg in ( '--rewrite', ):
        try:
            REWRITE_FILE = os.path.realpath(_args.pop(0))
            assert os.path.exists(REWRITE_FILE)
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )

    elif _arg in ( '-r', '--root' ):
        try:
            ROOT = os.path.realpath( _args.pop(0) ) + os.sep
            assert os.path.isdir( ROOT )
        except StopIteration:
            sys.exit( 'Error: %s requires a directory argument' % _arg )
        except:
            sys.exit( 'Error: invalid cache directory %s' % ROOT )
    elif _arg in ( '-v', '--verbose' ):
        VERBOSE += 1
    elif _arg in ( '-q', '--quiet' ):
        VERBOSE = 0 # FIXME: should have another threshold for logger perhaps,
        # and/or force warn or err and above to go somewhere.. syslog?
    elif _arg in ( '--nodir', ):
        _args.pop(0)
    elif _arg in ( '-t', '--timeout' ):
        try:
            TIMEOUT = int( _args.pop(0) )
            assert TIMEOUT > 0
        except:
            sys.exit( 'Error: %s requires a positive numerical argument' % _arg )
    elif _arg in ( '-6', '--ipv6' ):
        FAMILY = socket.AF_UNSPEC
    elif _arg == '--static':
        STATIC = True
    elif _arg == '--daemon':
        LOG = _args.pop(0)
    elif _arg == '--debug':
        DEBUG = True
    elif _arg in ('--pid-file',):
        PID_FILE = _args.pop(0)
    elif _arg == '--prune-gone':
        CMDS={'prune-gone':None}
    elif _arg == '--prune-stale':
        CMDS={'prune-stale':None}
    elif _arg == '--link-dupes':
        CMDS={'link-dupes':None}

    elif _arg in ('--list-locations',):
        CMDS={'list-locations':None}
    elif _arg in ('--list-resources',):
        CMDS={'list-resources':None}

    elif _arg in ('--print-record',):
        CMDS={'print-record':[_args.pop(0)]}

    elif _arg in ('--find-records',):
        CMDS={'find-records':[_args.pop(0)]}
    elif _arg in ('--check-joinlist',):
        CMDS={'check-join-rules':None}
    elif _arg in ('--run-join-rules',):
        CMDS={'run-join-rules':None}
    elif _arg in ('--check-cache',):
        CMDS={'check-cache':None}
#    elif _arg in ('--validate-cache',):
#        CHECK = 'validate'
    elif _arg in ('--check-files',):
        CMDS={'check-files':None}
    elif _arg in ('--data-dir',):
        path = _args.pop(0)
        assert os.path.isdir(path), path
        DATA_DIR = path + os.sep
    else:
        sys.exit( 'Error: invalid option %r' % _arg )


def log(msg, threshold=5):
    """
    Not much of a log..
    Output if VERBOSE >= threshold
    Use (r)syslog integer levels.
    """
    #assert not threshold == 0
    # see fiber.py which manages stdio
    if VERBOSE >= threshold:
        print msg


def format_info():
    """
    Return JSON for config.
    """
    return json_write({
        "htcache": {
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

descriptor_storage_type = None

def cn(obj):
    return obj.__class__.__name__

def print_str(s, l = 79):
    print_line = s.strip()
    hl = (l-7) / 2
    if len(print_line) > l:
        print_line = print_line[:hl] +' [...] '+ print_line[-hl:]
    return print_line

def run(cmds={}):
    for k, a in CMDS.items():
        if not isinstance(a, (list, tuple)):
            a = ()
        cmds[k](*a)
    sys.exit(0)
