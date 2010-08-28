import sys, os, socket

_args = iter( sys.argv )

PROG = _args.next()
PORT = 8080
ROOT = os.getcwd() + os.sep
VERBOSE = 0
TIMEOUT = 15
FAMILY = socket.AF_INET
FLAT = False
STATIC = False
ONLINE = True # useless 
LIMIT = False
LOG = False
DEBUG = False
MAXCHUNK = 1448 # maximum lan packet?
TIMEFMT = '%a, %d %b %Y %H:%M:%S GMT'
PARTIAL = '.incomplete'
DROP = '/etc/http-replicator/patterns.drop'
RESOURCE_DB = '/etc/http-replicator/resource.db'
CACHE = 'Cache.File'
USAGE = '''usage: %(PROG)s [options]

options:
  -h --help          show this help message and exit
  -p --port PORT     listen on this port for incoming connections, default %(PORT)i
  -r --root DIR      set cache root directory, default current: %(ROOT)s
  -c --cache TYPE    use module for caching, default %(CACHE)s. Also:
                     caches.FileTreeQ and FileTreeQH.
  -s --drop FILE    read regex patterns from file, default %(DROP)s.
  -v --verbose       increase output, use twice to show http headers
  -t --timeout SEC   break connection after so many seconds of inactivity, default %(TIMEOUT)i
  -6 --ipv6          try ipv6 addresses if available
     --flat          flat mode; cache all files in root directory (dangerous!)
     --static        static mode; assume files never change
     --offline       offline mode; never connect to server
     --limit RATE    limit download rate at a fixed K/s
     --log LOG       route output to log
     --debug         switch from gather to debug output module''' % locals()

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
      sys.exit( 'Error: %s requires an cache type' % _arg )
  elif _arg in ( '-s', '--drop' ):
    try:
      DROP = os.path.realpath( _args.next() )
    except:
      sys.exit( 'Error: %s requires an filename' % _arg )
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
  elif _arg in ( '-t', '--timeout' ):
    try:
      TIMEOUT = int( _args.next() )
      assert TIMEOUT > 0
    except:
      sys.exit( 'Error: %s requires a positive numerical argument' % _arg )
  elif _arg in ( '-6', '--ipv6' ):
    FAMILY = socket.AF_UNSPEC
  elif _arg == '--flat':
    FLAT = True
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
  elif _arg == '--log':
    LOG = _args.next()
  elif _arg == '--debug':
    DEBUG = True
  else:
    sys.exit( 'Error: invalid option %r' % _arg )


def log(msg, threshold=0):
  "Not much of a log.."
  # see fiber.py which manages stdio
  if VERBOSE > threshold:
    print msg

