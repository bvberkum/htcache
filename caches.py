import os, Cache, Params
try:
    from md5 import md5
except DeprecationWarning:
    from hashlib import md5



class FileTreeQ(Cache.File):

  def __init__( self, path ):
    super(FileTreeQ, self).__init__(path)

    sep = path.find( '?' )
    if sep != -1:
      path = path[ :sep ] + path[ sep: ].replace( '/', '%2F' )
      path = path[ :sep ] + path[ sep: ].replace( '%26', '/' )
      path = path[ :sep ] + path[ sep: ].replace( '&', '/' )
      path = path[ :sep ] + path[ sep: ].replace( ';', '/' )

    assert not Params.FLAT

    Params.log('Cache position: %s' % path)

    self.path = Params.ROOT + path
    self.file = None


class FileTreeQH(Cache.File):

  def __init__( self, path ):
    super(FileTreeQH, self).__init__(path)

    sep = path.find( '?' )
    if sep != -1:
        path = path[ :sep ] + os.sep + '#' + md5(path[sep:]).hexdigest()

    assert not Params.FLAT

    Params.log('Cache position: %s' % path)

    self.path = Params.ROOT + path
    self.file = None


class RefHash(Cache.File):

    def __init__(self, path):
        super(RefHash, self).__init__(path)
        self.refhash = md5(path).hexdigest()
        self.path = Params.ROOT + self.refhash
        self.file = None
        if not os.path.exists(Params.ROOT + Params.PARTIAL):
            os.mkdir(Params.ROOT + Params.PARTIAL)

    def open_new(self):
        self.path = Params.ROOT + Params.PARTIAL + os.sep + self.refhash
        Params.log('Preparing new file in cache: %s' % self.path)
        self.file = open( self.path, 'w+' )

    def open_full(self):
        self.path = Params.ROOT + self.refhash
        super(RefHash, self).open_full()

    def open_partial(self, offset=-1):
        self.path = Params.ROOT + Params.PARTIAL + os.sep + self.refhash
        self.mtime = os.stat( self.path ).st_mtime
        self.file = open( self.path, 'a+' )
        if offset >= 0:
            assert offset <= self.tell(), 'range does not match file in cache'
            self.file.seek( offset )
            self.file.truncate()
        Params.log('Resuming partial file in cache at byte %i' % self.tell())

    def remove_partial(self):
        self.path = Params.ROOT + Params.PARTIAL + os.sep + self.refhash
        os.remove( self.path )
        Params.log("Dropped partial file.")

    def partial( self ):
        self.path = Params.ROOT + Params.PARTIAL + os.sep + self.refhash
        return os.path.isfile( self.path ) and os.stat( self.path )

    def full( self ):
        self.path = Params.ROOT + self.refhash
        return os.path.isfile( self.path ) and os.stat( self.path )

    def close( self ):
        self.path = Params.ROOT + Params.PARTIAL + os.sep + self.refhash
        size = self.tell()
        self.file.close()
        if self.mtime >= 0:
            os.utime( self.path, ( self.mtime, self.mtime ) )
        if self.size == size:
            os.rename( self.path, Params.ROOT + self.refhash )
            Params.log('Finalized %s' % self.path)

