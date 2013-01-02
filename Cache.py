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
            # XXX: not in protocol?..
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
                    log("Warning: broken symlink, replacing: %s" % target,
                            Params.LOG_WARN)
                    os.unlink(rpath)

            # check if target is partial, rename
            i = 1
            if os.path.exists(rpath + Runtime.PARTIAL):
                while os.path.exists('%s.%s%s' % (rpath, i, Runtime.PARTIAL)):
                    i+=1
                shutil.copyfile(rpath+Runtime.PARTIAL, '%s.%s%s'
                        %(rpath,i,Runtime.PARTIAL))
                log("Warning: backed up duplicate incomplete %s" % i,
                        Params.LOG_WARN)
                # XXX: todo: keep largest partial only
            assert len(self.abspath()) < 255, \
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

        self.path = path
        self.file = None

    def abspath( self ):
        return os.path.join( Runtime.ROOT, self.path )

    def partial( self ):
        abspath = self.abspath()
        return os.path.isfile( abspath + Runtime.PARTIAL ) \
            and os.stat( abspath + Runtime.PARTIAL )

    def full( self ):
        abspath = self.abspath()
        return (
            ( os.path.islink( abspath ) and os.stat( os.readlink( abspath ) ) )
                or (os.path.isfile( abspath ) and os.stat( abspath )  )
            )

    def getsize(self):
        if self.partial():
            return os.path.getsize( self.abspath() + Runtime.PARTIAL )
        elif self.full():
            return os.path.getsize( self.abspath() )

    def open_new( self ):
        log('Preparing new file in cache', Params.LOG_INFO)
       
        tdir = os.path.dirname( self.abspath() )
        if not os.path.exists( tdir ):
            os.makedirs( tdir )

        try:
            self.file = open( self.abspath() + Runtime.PARTIAL, 'w+' )
        except Exception, e:
            log('Failed to open file: %s' %  e, Params.LOG_ERR)
            self.file = os.tmpfile()

    def open_partial( self, offset=-1 ):
        self.mtime = os.stat( self.abspath() + Runtime.PARTIAL ).st_mtime
        self.file = open( self.abspath() + Runtime.PARTIAL, 'a+' )
        if offset >= 0:
            assert offset <= self.tell(), 'range does not match file in cache'
            self.file.seek( offset )
            self.file.truncate()
        log('Resuming partial file in cache at byte %s' % self.tell(),
                Params.LOG_INFO)

    def open_full( self ):
        self.mtime = os.stat( self.abspath() ).st_mtime
        self.file = open( self.abspath(), 'r' )
        self.size = self.tell()

    def remove_full( self ):
        os.remove( self.abspath() )
        log('Removed complete file from cache', Params.LOG_NOTE)

    def remove_partial( self ):
        log('Removed partial file from cache', Params.LOG_NOTE)
        os.remove( self.abspath() + Runtime.PARTIAL )

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
            os.utime( self.abspath() + Runtime.PARTIAL, ( self.mtime, self.mtime ) )
        if self.size == size:
            os.rename( self.abspath() + Runtime.PARTIAL, self.abspath() )
            log("Finalized %r" % self.path, Params.LOG_NOTE)
        else:
            log("Closed partial %r" % self.path, Params.LOG_NOTE)

    def __nonzero__(self):
      return self.stat() != None

    def stat(self):
      return ( self.partial() or self.full() )

    def __del__( self ):
      try:
          self.close()
      except:
          pass


