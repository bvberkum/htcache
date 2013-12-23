"""
Params.CACHE can be set to Cache.File or a backend in this module ('caches.*')
For better support of some weird URLs the latter is preferable.

See README for description.
"""
import time, os
from hashlib import md5
import Cache, Params, Runtime
from util import *
import log


mainlog = log.get_log('main')


class FileTreeQ(Cache.File):
	"""
	Not only decode '/' in query part (after '?') but also
	after this encode arg=val pairs into directory names, suffixing
	the URL path with '?'.

	Also sorts query args/vals.
	"""

	def init(self, path):
		assert Params.PARTIAL not in path
		mainlog.debug("%s: init %r", self, path)
		psep = Runtime.ENCODE_PATHSEP
		# encode query and/or fragment parts
		sep = Cache.min_pos(path.find('#'), path.find( '?' )) 
		# sort query vals and turn into dirs
		if sep != -1:
			if psep:
				path = path[:sep] + path[sep:].replace('%2F', psep)
				path = path[:sep] + path[sep:].replace('/', psep)
			if '&' in path[sep:]:
				parts = path[sep+1:].split('&')
			elif ';' in path[sep:]:
				parts = path[sep+1:].split(';')
			else:
				parts = [path[sep+1:]]
			if Runtime.FileTreeQ_SORT:	
				parts.sort()
				while '' in parts:
					parts.remove('')
			path = path[ :sep+1 ]
			if parts:		
				path = path + '/' + '/'.join(parts)
		# optional removal of directories in path
		if psep:
			if sep == -1 or Runtime.FileTreeQ_ENCODE:
				# entire path
				path = path.replace( '/', psep)
			else:
				# URL path-part only
				path = path[:sep].replace( '/', psep) + path[sep:] 

		# make archive path	
		if Runtime.ARCHIVE:
			path = time.strftime( Runtime.ARCHIVE, time.gmtime() ) + path 
		
		# add default part
		if path[-1] == os.sep:
			path += Params.DEFAULT

		self.path = path
		self.file = None


class FileTreeQH(Cache.File):
	"""
	Convert entire query-part into md5hash, prefix by '#'.
	Sort query values before hashing.
	ENCODE_PATHSEP is applied after hashing query, before ARCHIVE.
	"""

	def init(self, path):
		assert Params.PARTIAL not in path
		mainlog.debug("%s: init %r", self, path)
		# encode query if present
		sep = path.find( '?' )
		# other encoding in query/fragment part		
		if sep != -1:
			if '&' in path[sep:]:
				qsep='&'
				parts = path[sep:].split('&')
			elif ';' in path[sep:]:
				qsep=';'
				parts = path[sep:].split(';')
			else:
				qsep=''
				parts = [path[sep:]]
			parts.sort()	 
			path = path[ :sep ] + os.sep + '#' + md5(qsep.join(parts)).hexdigest()
		# optional removal of directories in entire path
		psep = Runtime.ENCODE_PATHSEP
		if psep:
			path = path.replace( '/', psep)
		# make archive path	
		if Runtime.ARCHIVE:
			path = time.strftime( Runtime.ARCHIVE, time.gmtime() ) + path 
		
			# add default part
			if path[-1] == os.sep:
				path += Params.DEFAULT

		self.path = path
		self.file = None


class PartialMD5Tree(Cache.File):
	def init(self, path):
		assert Params.PARTIAL not in path
		mainlog.debug("%s: init %r", self, path)
		if Runtime.ARCHIVE:
			path = time.strftime( Runtime.ARCHIVE, time.gmtime() ) + path 

		s = Params.MAX_PATH_LENGTH - 34 - len(Runtime.ROOT)
		if len(path) + len(Runtime.ROOT) > Params.MAX_PATH_LENGTH:
			path = path[:s] + os.sep + '#' + md5(path[s:]).hexdigest()
		
		# add default part
		if path[-1] == os.sep:
			path += Params.DEFAULT

		self.path = path			

class FileTree(FileTreeQ, FileTreeQH, PartialMD5Tree):
	def init(self, path):
		assert Params.PARTIAL not in path
		mainlog.debug("%s: init %r", self, path)
		path2 = path
		if Runtime.ARCHIVE:
			path2 = time.strftime( Runtime.ARCHIVE, time.gmtime() ) + path2
		path2 = os.path.join(Runtime.ROOT, path2)
		if len(path2) >= Params.MAX_PATH_LENGTH:
			sep = Cache.min_pos(path2.find('#'), path2.find( '?' )) 
			if sep != -1:
				if (len(path2[:sep])+34) < Params.MAX_PATH_LENGTH:
					FileTreeQH.init(self, path)
				else:
					PartialMD5Tree.init(self, path)
		else:					
			FileTreeQ.init(self, path)

	def __str__(self):
		return "[FileTree %s]" % hex(id(self))


class RefHash(Cache.File):

	def __init__(self, path):
		mainlog.debug("RefHash.__init__ %r", path)
		super(RefHash, self).__init__(path)
		self.refhash = md5(path).hexdigest()
		self.path = self.refhash
		self.file = None
		if not os.path.exists(Runtime.ROOT + Runtime.PARTIAL):
			os.mkdir(Runtime.ROOT + Runtime.PARTIAL)

	def open_new(self):
		self.path = Runtime.PARTIAL + os.sep + self.refhash
		mainlog.debug('%s: Preparing new file in cache: %s', self, self.path)
		self.file = open( self.abspath(), 'w+' )

	def open_full(self):
		self.path = self.refhash
		super(RefHash, self).open_full()

	def open_partial(self, offset=-1):
		self.path = Runtime.PARTIAL + os.sep + self.refhash
		self.mtime = os.stat( self.abspath() ).st_mtime
		self.file = open( self.abspath() , 'a+' )
		if offset >= 0:
			assert offset <= self.tell(), 'range does not match file in cache'
			self.file.seek( offset )
			self.file.truncate()
		mainlog.info('Resuming partial file in cache at byte %i', self.tell())

	def remove_partial(self):
		self.path = Runtime.PARTIAL + os.sep + self.refhash
		os.remove( self.abspath() )
		mainlog.note("Dropped partial file.")

	def partial( self ):
		self.path = Runtime.PARTIAL + os.sep + self.refhash
		return os.path.isfile( self.abspath() ) and os.stat( self.abspath() )

	def full( self ):
		self.path = self.refhash
		return os.path.isfile( self.abspath() ) and os.stat( self.abspath() )


