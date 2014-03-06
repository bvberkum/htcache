import time, os, sys
import Params


def load_backend_type(tp):
	assert '.' in tp, "Specify backend as <module>.<backend-type>"
	p = tp.split( '.' )
	path, name = '.'.join( p[:-1] ), p[-1]
	mod = __import__( path, locals(), globals(), [] )
	return getattr( mod, name )


def makedirs( path ):
	dirpath = os.path.dirname( path )
	if dirpath and not os.path.isdir( dirpath ):
		if os.path.isfile( dirpath ):
			print 'directory %s mistaken for file' % dirpath
			os.remove( dirpath )
		else:
			makedirs( dirpath )
		os.mkdir( dirpath )


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
		super( File, self ).__init__()
		if path:
			self.init( path )
			#assert len(self.path) < 255, \
			#		"LBYL, cache location path to long for Cache.File! "

	def init(self, path):
		assert not path.startswith(os.sep), \
			"FIXME: implement saving in other roots"
		# encode query and/or fragment parts
		sep = min_pos(path.find('#'), path.find( '?' ))
		# optional removal of directories in entire path
		psep = Params.ENCODE_PATHSEP
		if psep:
			path = path.replace( '/', psep)
		else:
			# partial pathsep encode
			if sep != -1:
				path = path[ :sep ] + path[ sep: ].replace( '/', psep)
		# make archive path
		if Params.ARCHIVE:
			path = time.strftime( Params.ARCHIVE, time.gmtime() ) + path
		self.path = os.path.join(Params.ROOT, path)
		self.file = None

	def partial( self ):
		return os.path.isfile( self.path + Params.PARTIAL ) \
			and os.stat( self.path + Params.PARTIAL )

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

	def __nonzero__(self):
	  return self.partial() or self.full()

	def __del__( self ):
	  try:
		  self.close()
	  except:
		  pass


