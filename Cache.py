import Params, os


def load_backend(tp):
    if '.' in tp:
        p = tp.split('.')
        path, name = '.'.join(p[:-1]), p[-1]
    else:
        path = tp
        name = tp

    mod = __import__(path, locals(), globals(), [])
    return getattr(mod, name)


def makedirs( path ):

  dir = os.path.dirname( path )
  if dir and not os.path.isdir( dir ):
    if os.path.isfile( dir ):
      print 'directory %s mistaken for file' % dir
      os.remove( dir )
    else:
      makedirs( dir )
    os.mkdir( dir )


class File(object):

  size = -1
  mtime = -1

  def __init__( self, path ):
    super(File, self).__init__()

    sep = path.find( '?' )
    if sep != -1:
      path = path[ :sep ] + path[ sep: ].replace( '/', '%2F' )
    if Params.FLAT:
      path = os.path.basename( path )
    #if Params.VERBOSE:
    #  print 'Cache position:', path

    self.path = Params.ROOT + path
    self.file = None

  def partial( self ):

    return os.path.isfile( self.path + Params.PARTIAL ) and os.stat( self.path + Params.PARTIAL )

  def full( self ):

    return os.path.isfile( self.path ) and os.stat( self.path )

  def open_new( self ):

    if Params.VERBOSE:
      print 'Preparing new file in cache'
    try:
      makedirs( self.path )
      self.file = open( self.path + Params.PARTIAL, 'w+' )
    except Exception, e:
      print 'Failed to open file:', e
      self.file = os.tmpfile()

  def open_partial( self, offset=-1 ):

    self.mtime = os.stat( self.path + Params.PARTIAL ).st_mtime
    self.file = open( self.path + Params.PARTIAL, 'a+' )
    if offset >= 0:
      assert offset <= self.tell(), 'range does not match file in cache'
      self.file.seek( offset )
      self.file.truncate()
    if Params.VERBOSE:
      print 'Resuming partial file in cache at byte', self.tell()

  def open_full( self ):

    self.mtime = os.stat( self.path ).st_mtime
    self.file = open( self.path, 'r' )
    self.size = self.tell()
    if Params.VERBOSE:
      print 'Reading complete file from cache'

  def remove_full( self ):

    os.remove( self.path )
    print 'Removed complete file from cache'

  def remove_partial( self ):

    print 'Removed partial file from cache'
    os.remove( self.path + Params.PARTIAL )

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
      os.utime( self.path + Params.PARTIAL, ( self.mtime, self.mtime ) )
    if self.size == size:
      os.rename( self.path + Params.PARTIAL, self.path )
      if Params.VERBOSE:
        print 'Finalized', self.path

  def __del__( self ):

    try:
      self.close()
    except:
      pass
