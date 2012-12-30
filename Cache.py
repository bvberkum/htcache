import time, os, sys, shutil

import Params
import Runtime
import Rules
from util import *


def load_backend_type(tp):
    assert '.' in tp, "Specify backend as <module>.<backend-type>"
    p = tp.split( '.' )
    path, name = '.'.join( p[:-1] ), p[-1]
    mod = __import__( path, locals(), globals(), [] )
    return getattr( mod, name )


def min_pos(*args):
    "Return smallest of all arguments (but >0)"
    r = sys.maxint
    for a in args:
        if a > -1:
            r = min( a, r )
    return r


class File(object):
    """
    Simple cache that stores at path/filename take from URL.
    The PARTIAL suffix (see Params) is used for partial downloads.

    Parameters ARCHIVE and ENCODE_PATHSEP also affect the storage location.
    ARCHIVE is applied after ENCODE_PATHSEP.
    """
    size = -1
    mtime = -1

    def __init__(self, path=None):
        """
        The path is an `wget -r` path. Meaning it has the parts:
        host/path?query. The cache implementation will determine the final
        local path name. 
        """
        super( File, self ).__init__()
        os.chdir(Runtime.ROOT)
        if path:
            rpath = self.apply_rules(path)
            self.init(rpath)
            # symlink to rewritten path
            #if path != rpath and not os.path.exists(path):
            #    log("Symlink: %s -> %s" %(path, rpath))
            #    os.makedirs(os.path.dirname(path))
            #    os.symlink(rpath, path)
            # check if target is symlink, must exist
            if os.path.islink(rpath):
                target = os.readlink(rpath)
                if not os.path.exists(target):
                    log("Warning: broken symlink, replacing: %s" % target)
                    os.unlink(rpath)
            # check if target is partial, rename
            i = 1
            if os.path.exists(rpath + Runtime.PARTIAL):
                while os.path.exists('%s.%s%s' % (rpath, i, Runtime.PARTIAL)):
                    i+=1
                shutil.copyfile(rpath+Runtime.PARTIAL, '%s.%s%s'
                        %(rpath,i,Runtime.PARTIAL))
                log("Warning: backed up duplicate incomplete %s" % i)
                # XXX: todo: keep largest partial only
            assert len(self.path) < 255, \
                    "LBYL, cache location path to long for Cache.File! "

    def apply_rules(self, path):
        """
        Apply rules for path.
        """
        path = Rules.Join.rewrite(path)
        return path

    def init(self, path):
        assert not path.startswith(os.sep), \
                "File.init: saving in other roots not supported,"\
                " only paths relative to Runtime.ROOT allowed."

        # encode query and/or fragment parts
        sep = min_pos(path.find('#'), path.find( '?' ))
        # optional removal of directories in entire path
        psep = Runtime.ENCODE_PATHSEP
        if psep:
            path = path.replace( '/', psep)
        else:
            # partial pathsep encode
            if sep != -1:
                path = path[ :sep ] + path[ sep: ].replace( '/', psep)
        # make archive path
        if Runtime.ARCHIVE:
            path = time.strftime( Runtime.ARCHIVE, time.gmtime() ) + path

        self.path = os.path.join(Runtime.ROOT, path)
        self.file = None

    def partial( self ):
        return os.path.isfile( self.path + Runtime.PARTIAL ) \
            and os.stat( self.path + Runtime.PARTIAL )

    def full( self ):
        return (
            ( os.path.islink( self.path ) and os.stat(os.readlink(self.path)) )
                or (os.path.isfile( self.path ) and os.stat( self.path )  )
            )

    def getsize(self):
        if self.partial():
            return os.path.getsize( self.path + Runtime.PARTIAL )
        elif self.full():
            return os.path.getsize( self.path )

    def open_new( self ):
        if Runtime.VERBOSE:
            print 'Preparing new file in cache'
       
        tdir = os.path.dirname( self.path )
        if not os.path.exists( tdir ):
            os.makedirs( tdir )

        try:
            self.file = open( self.path + Runtime.PARTIAL, 'w+' )
        except Exception, e:
            print 'Failed to open file:', e
            self.file = os.tmpfile()

    def open_partial( self, offset=-1 ):
        self.mtime = os.stat( self.path + Runtime.PARTIAL ).st_mtime
        self.file = open( self.path + Runtime.PARTIAL, 'a+' )
        if offset >= 0:
            assert offset <= self.tell(), 'range does not match file in cache'
            self.file.seek( offset )
            self.file.truncate()
        if Runtime.VERBOSE:
            print 'Resuming partial file in cache at byte', self.tell()

    def open_full( self ):
        self.mtime = os.stat( self.path ).st_mtime
        self.file = open( self.path, 'r' )
        self.size = self.tell()

    def remove_full( self ):
        os.remove( self.path )
        log('Removed complete file from cache')

    def remove_partial( self ):
        log('Removed partial file from cache')
        os.remove( self.path + Runtime.PARTIAL )

    def read( self, pos, size ):
        self.file.seek( pos )
        return self.file.read( size )

    def write( self, chunk ):
        self.file.seek( 0, 2 )
        return self.file.write( chunk )

    def tell( self ):
        self.file.seek( 0, 2 )
        return self.file.tell()

    def close( self ):
        size = self.tell()
        self.file.close()
        if self.mtime >= 0:
            os.utime( self.path + Runtime.PARTIAL, ( self.mtime, self.mtime ) )
        if self.size == size:
            os.rename( self.path + Runtime.PARTIAL, self.path )
            log("Finalized %r" % self.path)
        else:
            log("Closed partial %r" % self.path)

    def __nonzero__(self):
      return self.partial() or self.full()

    def __del__( self ):
      try:
          self.close()
      except:
          pass


