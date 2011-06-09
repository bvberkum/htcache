import sys, os, socket


_args = iter( sys.argv )

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
DROP = '/etc/htcache/rules.drop'
NOCACHE = '/etc/htcache/rules.nocache'
SORT = '/etc/htcache/rules.sort'
HTML_PLACEHOLDER = '/var/lib/htcache/filtered-placeholder.html'
IMG_PLACEHOLDER = '/var/lib/htcache/forbidden-sign.png'
#CACHE = 'Cache.File'
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
RESOURCES = '/var/lib/htcache/resource.db'
SHA1SUM = '/var/cache/sha1sum/'
#TODO CRC, par2?
#PAR2 = '/var/cache/par2/'
# query params
PRINT_RECORD = []
PRINT_ALLRECORDS = False
FIND_RECORDS = {}
PRINT_MEDIA = []
DHTML_CLIENT = True

cache_options = 'ARCHIVE', 'ENCODE_PATHSEP', 'SORT_QUERY_ARGS', 'ENCODE_QUERY'

# maintenance params
CHECK_DESCRIPTOR = []

#     --flat          flat mode; cache all files in root directory (dangerous!)

USAGE = '''usage: %(PROG)s [options]

  -h --help          show this help message and exit

proxy options:
  -p --port PORT     listen on this port for incoming connections, default %(PORT)i
  -r --root DIR      set cache root directory, default current: %(ROOT)s
  -a --archive FMT   prefix cache location by a formatted datetime. 
                     ie. store a new copy every hour, day, etc. 
  -c --cache TYPE    use module for caching, default %(CACHE)s. 
  -D --nodir SEP     replace unix path separator, ie. don't create a directory
                     tree. does not encode `archive` prefix.
  TODO --encode query sep                   
  -s --sha1sum DIR   maintain an index with the SHA1 checksum for each resource
  -d --drop FILE     filter requests for URI's based on regex patterns. 
                     read line for line from file, default %(DROP)s.
  TODO -n --nocache FILE  bypass caching for requests based on regex pattern.
  -s --sort SORT     sort requests based on regex, directory-name pairs from file.
                     unmatched requests are cached normally.
  -v --verbose       increase output, use twice to show http headers
  -t --timeout SEC   break connection after so many seconds of inactivity, default %(TIMEOUT)i
  -6 --ipv6          try ipv6 addresses if available
     --static        static mode; assume files never change
     --offline       offline mode; never connect to server
     --limit RATE    limit download rate at a fixed K/s
     --daemon LOG    daemonize process and print PID, route output to LOG
     --debug         switch from gather to debug output module

cache maintenance:
     TODO --prune-stale
                     Delete outdated cached resources.
     TODO --prune-gone
                     Remove resources no longer online.

resource queries:
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
     
resource maintenance:     
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
    elif _arg in ( '-c', '--cache' ):
        try:
            CACHE = _args.next()
        except:
            sys.exit( 'Error: %s requires an cache type argument' % _arg )
    elif _arg in ( '-d', '--drop' ):
        try:
            DROP = os.path.realpath( _args.next() )
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )
    elif _arg in ( '-n', '--nocache' ):
        try:
            NOCACHE = os.path.realpath( _args.next() )
            #assert os.path.exists(NOCACHE)
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )
    elif _arg in ( '-s', '--sort' ):
        try:
            SORT = os.path.realpath( _args.next() )
            #assert os.path.exists(SORT)
        except:
            sys.exit( 'Error: %s requires an filename argument' % _arg )
    elif _arg in ( '-s', '--sha1sum' ):
        try:
            ROOT = os.path.realpath( _args.next() ) + os.sep
            assert os.path.isdir( ROOT )
        except StopIteration:
            sys.exit( 'Error: %s requires a directory argument' % _arg )
        except:
            sys.exit( 'Error: invalid sha1sum directory %s' % ROOT )
    elif _arg in ( '-r', '--root' ):
        try:
            ROOT = os.path.realpath( _args.next() ) + os.sep
            assert os.path.isdir( ROOT )
        except StopIteration:
            sys.exit( 'Error: %s requires a directory argument' % _arg )
        except:
            sys.exit( 'Error: invalid cache directory %s' % ROOT )
    elif _arg in ( '-a', '--archive' ):
        ARCHIVE = _args.next()
    elif _arg in ( '-D', '--nodir' ):
        ENCODE_PATHSEP = _args.next()
    elif _arg in ( '-v', '--verbose' ):
        VERBOSE += 1
    elif _arg in ( '-t', '--timeout' ):
        try:
            TIMEOUT = int( _args.next() )
            assert TIMEOUT > 0
        except:
            sys.exit( 'Error: %s requires a positive numerical argument' % _arg )
    elif _arg in ( '-6', '--ipv6' ):
        FAMILY = socket.AF_UNSPEC
#  elif _arg == '--flat':
#    FLAT = True
    elif _arg == '--static':
        STATIC = True
    elif _arg == '--offline':
        ONLINE = False
        STATIC = True
    elif _arg == '--limit':
        try:
            LIMIT = float( _args.next() ) * 1024
        except:
            sys.exit( 'Error: %s requires a numerical argument' % _arg )
    elif _arg == '--daemon':
        LOG = _args.next()
    elif _arg == '--debug':
        DEBUG = True

# resource queries
    elif _arg == '--print-info':
        PRINT_RECORD.append(_args.next())
    elif _arg == '--print-all-info':  
        PRINT_ALLRECORDS = True  
    #elif '--print-record'  
    #elif '--print-mode'  
    #elif '--print-path'  
    #elif '--print-url'  
    elif _arg == '--find-info':  
        args = _args.next()
        _find={}
        for a in args.split(','):
            p = a.find(':')
            k, a = a[:p], a[p+1:]
            if ':' in a and not k == 'srcref':
                p = a.find(':')
                k2, a = a[:p], a[p+1:]
                if k not in _find:
                    _find[k] = {}
                _find[k][k2] = a
            else:
                _find[k] = a
        FIND_RECORDS.update(_find)
    elif _arg.startswith('--print-'):
        if _arg[8:] == 'documents':
            PRINT_MEDIA.append('documents')
        elif _arg[8:] == 'images':
            PRINT_MEDIA.append('images')
        elif _arg[8:] == 'audio':
            PRINT_MEDIA.append('audio')
        elif _arg[8:] == 'videos':
            PRINT_MEDIA.append('videos')

# cache maintenance
    elif _arg.startswith('--prune-stale'):
        pass

# resource maintenance
    elif _arg.startswith('--check-'):
        if _arg[8:] == 'mediatypes':
            CHECK_DESCRIPTOR.append('mediatypes')
        elif _arg[8:] == 'encodings':
            CHECK_DESCRIPTOR.append('encodings')
        elif _arg[8:] == 'mediatypes':
            CHECK_DESCRIPTOR.append('mediatypes')
    #elif _arg == '--force-fix':

    else:
        sys.exit( 'Error: invalid option %r' % _arg )


def log(msg, threshold=0):
  "Not much of a log.."
  # see fiber.py which manages stdio
  if VERBOSE > threshold:
    print msg

