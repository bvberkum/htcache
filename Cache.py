import Runtime, os


def makedirs( path):

	dir = os.path.dirname( path )
	if dir and not os.path.isdir( dir):
		if os.path.isfile( dir):
			print 'directory %s mistaken for file' % dir
			os.remove( dir )
		else:
			makedirs( dir )
		os.mkdir( dir )


class File:

	size = -1
	mtime = -1

	def __init__(self, path):

		sep = path.find( '?' )
		if sep != -1:
			path = path[ :sep ] + path[ sep: ].replace( '/', '%2F' )
			path = path[ :sep ] + path[ sep: ].replace( '%26', '/' )
			path = path[ :sep ] + path[ sep: ].replace( '&', '/' )
			path = path[ :sep ] + path[ sep: ].replace( ';', '/' )
		if Runtime.FLAT:
			path = os.path.basename( path )
		if Runtime.VERBOSE:
			print 'Cache position:', path

		self.__path = Runtime.ROOT + path
		print self.__path	
		self.fp = None

	def partial(self):

		return os.path.isfile( self.__path + Runtime.PARTIAL ) and os.stat(self.__path + Runtime.PARTIAL )

	def full(self):

		return os.path.isfile( self.__path ) and os.stat( self.__path )

	def open_new(self):

		if Runtime.VERBOSE:
			print 'Preparing new file in cache'
		try:
			makedirs(self.__path )
			self.fp = open(self.__path + Runtime.PARTIAL, 'w+' )
		except Exception, e:
			print 'Failed to open file:', e
			self.fp = os.tmpfile()

	def open_partial(self, offset=-1):

		self.mtime = os.stat(self.__path + Runtime.PARTIAL ).st_mtime
		self.fp = open(self.__path + Runtime.PARTIAL, 'a+' )
		if offset >= 0:
			assert offset <= self.tell(), 'range does not match file in cache'
			self.fp.seek( offset )
			self.fp.truncate()
		if Runtime.VERBOSE:
			print 'Resuming partial file in cache at byte', self.tell()

	def open_full(self):

		self.mtime = os.stat(self.__path ).st_mtime
		self.fp = open(self.__path, 'r' )
		self.size = self.tell()
		if Runtime.VERBOSE:
			print 'Reading complete file from cache'

	def remove_full(self):
		os.remove(self.__path)
		mainlog.note('%s: Removed complete file from cache', self)

	def remove_partial(self):
		mainlog.note('%s: Removed partial file from cache', self)
		os.remove(self.__path + Runtime.PARTIAL)

	def read(self, pos, size):
		self.fp.seek( pos )
		return self.fp.read( size )

	def write(self, chunk):
		self.fp.seek( 0, 2 )
		return self.fp.write( chunk )

	def tell(self):
		self.fp.seek( 0, 2 )
		return self.fp.tell()

	def close(self):

		size = self.tell()
		self.fp.close()
		if self.mtime >= 0:
			os.utime(self.__path + Runtime.PARTIAL, (self.mtime, self.mtime ) )
		if self.size == size:
			os.rename(self.__path + Runtime.PARTIAL, self.__path )
			if Runtime.VERBOSE:
				print 'Finalized', self.__path

	def __del__(self):

		try:
			self.close()
		except:
			pass
