"""
TODO:
- Reimplement NODIR
- Option to merge path elements into one directory while file count
  is below treshold.
"""
import time, os, sys, shutil
import re

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


def suffix_ext(path, suffix):
    x = re.match('.*\.([a-zA-Z0-9]+)$', path)
    if x:
        p = x.start(1)
        path = path[:p-1] + suffix + path[p-1:]
    return path      


class File(object):

    """
    Simple cache that stores at path/filename taken from URL.
    The PARTIAL suffix (see Params) is used for partial downloads.

    Parameters ARCHIVE and ENCODE_PATHSEP also affect the storage location.
    ARCHIVE is applied after ENCODE_PATHSEP.
    """

    def __init__(self, path=None):
        """
        The path is an `wget -r` path. Meaning it has the parts:
        host/path?query. The cache implementation will determine the final
        local path name. 
        """
        super( File, self ).__init__()
        self.size = -1
        self.mtime = -1
        self.partial = None
        self.full = None
        if path:
            self.init(path)

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

        assert len(self.abspath()) < 255, \
                "LBYL, cache location path to long for Cache.File! "

        self.stat()

    def stat( self ):
        abspath = os.path.join( Runtime.ROOT, self.path )
        partial = suffix_ext( abspath, Runtime.PARTIAL )
        if os.path.isfile( partial ):
            self.partial = os.stat( partial )
            self.full = False
        elif os.path.isfile( abspath ):
            self.full = os.stat( abspath )
            self.partial = False
        return self.partial or self.full

    def abspath( self ):
        abspath = os.path.join( Runtime.ROOT, self.path )
        if self.full:
            return abspath
        else:
            return suffix_ext( abspath, Runtime.PARTIAL )

#    def getsize(self):
#        return (self.partial or self.full).st_size

    def open_new( self ):
        log('Preparing new file in cache', Params.LOG_INFO)
    
        new_file = self.abspath()
        
        tdir = os.path.dirname( new_file )
        if not os.path.exists( tdir ):
            os.makedirs( tdir )

        try:
            self.file = open( new_file, 'w+' )
        except Exception, e:
            log('Failed to open file: %s' %  e, Params.LOG_ERR)
            self.file = os.tmpfile()

    def open_partial( self, offset=-1 ):
        self.file = open( self.abspath(), 'a+' )
        if offset >= 0:
            assert offset <= self.tell(), 'range does not match file in cache'
            self.file.seek( offset )
            self.file.truncate()
        log('Resuming partial file in cache at byte %s' % self.tell(),
                Params.LOG_INFO)

    def open_full( self ):
        self.file = open( self.abspath(), 'r' )
        self.size = self.tell()

    def open( self ):
        if self.full:
            self.open_full()
        elif self.partial:
            self.open_partial()
        else:
            self.open_new()

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
        if self.size == size:
            if self.partial:
                abspath = os.path.join( Runtime.ROOT, self.path )
                os.rename( 
                        suffix_ext( abspath, Runtime.PARTIAL ),
                        abspath  )
                if self.mtime >= 0:
                    os.utime( abspath, ( self.mtime, self.mtime ) )
                self.stat()
                assert self.full
                log("Finalized %r" % self.path, Params.LOG_NOTE)
        else:
            log("Closed partial %r" % self.path, Params.LOG_NOTE)
#
#    def __nonzero__(self):
#      return ( self.complete() or self.partial ) != None

    def __del__( self ):
      try:
          self.close()
      except:
          pass


