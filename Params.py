import os, re, socket, sys


_args = iter( sys.argv )

VERSION = 0.3

# proxy params
PROG = _args.next()
PORT = 8080
ROOT = os.getcwd() + os.sep
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
SORT = []
SORT_FILE = '/etc/htcache/rules.sort'
HTML_PLACEHOLDER = '/var/lib/htcache/filtered-placeholder.html'
IMG_PLACEHOLDER = '/var/lib/htcache/forbidden-sign.png'
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
#BACKEND = '/var/lib/htcache/resource.db'
#BACKEND = 'sqlite:///var/lib/htcache/resource.sqlite'
BACKEND = 'mysql://root:MassRootSql@robin/taxus_o'
#BACKENDS = { # name: test, type }
#BD_IDX_TEST, BD_IDX_TYPE = 0, 1
#SHA1SUM = '/var/cache/sha1sum/'
#PAR2 = '/var/cache/par2/'
DBDIR = '/var/lib/htcache/'
RESOURCES = '/var/lib/htcache/resource.db'
# query params
PRINT_RECORD = []
PRINT_ALLRECORDS = False
PRINT_MEDIA = []
DHTML_CLIENT = True

cache_options = 'ARCHIVE', 'ENCODE_PATHSEP', 'SORT_QUERY_ARGS', 'ENCODE_QUERY'

# maintenance params
CHECK_DESCRIPTOR = []

#     --flat          flat mode; cache all files in root directory (dangerous!)
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
  -c --cache TYPE    use module for caching, default %(CACHE)s.
  -b --backend REF   initialize metadata backend from reference, default
                     %(BACKEND)s.

Rules:
  -d --drop FILE     filter requests for URI's based on regex patterns.
                     read line for line from file, default %(DROP_FILE)s.
  -n --nocache FILE  TODO: bypass caching for requests based on regex pattern.

Misc.:
  -t --timeout SEC   break connection after so many seconds of inactivity,
                     default %(TIMEOUT)i
  -6 --ipv6          try ipv6 addresses if available
  -v --verbose       increase output, use twice to show http headers


See the documentation in ReadMe regarding configuration of the proxy. The
following options don't run the proxy but access the cache and descriptor backend::

Resources:
     --print-info FILE
     --print-all-info
                     Print the resource record(s) for (each) cache location,
                     then exit.
     --print-record
                     Print all record info; tab separated, one per line.
                     This is the default.
     FIXME --print-mode line|tree
     TODO --print-url
     TODO --print-path
                     List either URLs or PATHs only, omit record data.
     --find-info KEY:[KEY:]ARG[,...]
                     Search for exact record matches.
     --print-documents
     --print-videos
     --print-audio
     --print-images
                     Search through predefined list of content-types.

Maintenance:
     --prune-stale   TODO: Delete outdated cached resources.
     --prune-gone    TODO: Remove resources no longer online.
     TODO --check-exists
                     Prune outdated resources or resources that are no longer online.

     TODO --check-encodings
     TODO --check-languages
     TODO --check-mediatypes
                     Use some heurisics to get a better value and replace
                     previous setting on obvious matches, otherwise prompt user.
     TODO --x-force-fix
                     Use first likely value for
                     check-encodings/languages/mediatypes.
     TODO --check-dupes
                     Symlink duplicate content, check by size and hash.
                     Requires up to data hash index.
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
    elif _arg in ( '-b', '--backend' ):
        try:
            BACKEND = _args.next()
        except:
            sys.exit( 'Error: %s requires an backend-reference for argument' % _arg )
    elif _arg in ( '-c', '--cache' ):
        try:
            CACHE = _args.next()
        except:
            sys.exit( 'Error: %s requires an cache type argument' % _arg )
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


if __name__ == '__main__':
	parse_joinlist()
	validate_joinlist()
