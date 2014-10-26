"""
Resource storage and descriptor facade.

"""
import anydbm, os, urlparse
import time
import calendar
from os.path import join

try:
	# Py >= 2.4
	assert set
except AssertionError:
	from sets import Set as set

from sqlalchemy import Column, Integer, String, Boolean, Text, \
	ForeignKey, Table, Index, DateTime, Float, \
	create_engine
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, sessionmaker

import Cache
import Params
import HTTP
import Rules
import Runtime
from util import *
from error import *
from pprint import pformat
import log


mainlog = log.get_log('main')


class ProxyData(object):

	"""
	A facade for instances in datastore seen from a Descriptor instance.

	Web Resources::

		{ <res-uri> : <Resource(

		   host, path, meta, cache

		)> }
	
	Map of broken loations that could not be retrieved::

		{ <res-uri> : <status>, <keep-boolean> }
	
	Cache descriptors::

		{ <cache-location> : <Descriptor(

			hash, mediatype, charset, language, size, quality

		) }

	Map of uriref to cache locations (reverse for resources)::

		{ <cache-location> : <res-uri> }

	Qualified relations 'rel' from 'res' to 'ref'::

		relations_to = { <res-uri> => *( <rel-uri>, <ref-uri> ) }
	
	Reverse mapping, the qualification will be in relations_to::

		relations_from = { <ref-uri> => *<res-uri> }
	"""

	def __init__( self, protocol ):
		self.protocol = protocol
		self.descriptor = None 
		self.cache = None
	
		self.mtime = None

		mainlog.debug("%s: empty instance", self)

	def set_content_length(self, value):
		if self.cache.file:
			assert self.cache.size == int( value ),\
				( self.cache.size, int( value ) )
		self.descriptor.size = int( value )

	def set_last_modified(self, value):
		mtime = None
		try:
			mtime = calendar.timegm( time.strptime(
				value, Params.TIMEFMT ) )
		except:
			mainlog.err( 'Error: illegal time format in Last-Modified: %s.', value )
			# XXX: Try again, should make a list of alternate (but invalid) date formats
			try:
				tmhdr = re.sub(
						'\ [GMT0\+-]+$', 
						'',
						value)
				mtime = calendar.timegm( time.strptime(
					tmhdr, 
					Params.TIMEFMT[:-4] ) )
			except:
				try:
					mtime = calendar.timegm( time.strptime(
						value,
						Params.ALTTIMEFMT ) )
				except:
					mainlog.err( 'Fatal: unable to parse Last-Modified: %s.', value )
		
		if mtime:
			self.descriptor.mtime = mtime
# XXX:			if self.cache.stat():
#				self.cache.utime( mtime )

	def get_last_modified(self):
		if self.descriptor.mtime >= 0:
			mtime = self.descriptor.mtime
		else:
			mtime = self.cache.mtime
		return time.strftime(
					Params.TIMEFMT, time.gmtime( mtime ) )

	def get_content_location(self):
		return self.descriptor.resource.url

	def set_content_location(self, url):
		self.descriptor.resource.url = url

	def set_content_type(self, value):
		data = {}
		if ';' in value:
			v = value.split(';')
			data['mediatype'] = v.pop(0).strip()
			while v:
				hp = v.pop(0).strip().split('=')
				param_name, param_value = hp[0].strip(), hp[1].strip()
				attr_type, attr_name = self._attr_map[param_name]
				data[attr_name] = attr_type(param_value)
		else:
			data['mediatype'] = value.strip()
		while data:
			k = data.keys()[0]
			setattr( self.descriptor, k, data[k] )
			del data[k]

	def get_content_type(self):
		mediatype = self.descriptor.mediatype
		if self.descriptor.charset:
			mediatype += '; charset=%s' % self.descriptor.charset
		if self.descriptor.quality:
			mediatype += '; qs=%i' % self.descriptor.quality
		return mediatype

	def init_data(self, url):
		"""
		Fetch existing or pre-initialize new Descriptor instance
		before we have any content data available.
		XXX: The associated resource should be initalized later.
		"""
		assert not self.descriptor or not ( self.descriptor.mtime or self.descriptor.path or self.descriptor.size ), ( self.descriptor.mtime, self.descriptor.path, self.descriptor.size )

		self.descriptor = Descriptor.find_latest(url)
		if not self.descriptor or not self.descriptor.id:
			self.descriptor = Descriptor()
			mainlog.debug('%s: Initialized new descriptor. ', self)
		else:
			mainlog.debug('%s: Found existing descriptor for %r ', self, self.descriptor.path)

	def exists( self ):
		return self.descriptor != None and self.descriptor.id != None

	def is_open( self ):
		return self.cache and self.cache.file != None

	def init_cache( self, netpath=None ):
		"""
		The location will be subject to the specific heuristics of the backend
		type, this path will be readable from cache.path.
		"""
		mainlog.debug( "%s: Init cache: %s", self, Runtime.CACHE )
		self.cache = Cache.load_backend_type( Runtime.CACHE )()
		if netpath:
			assert netpath[:2] == '//', netpath
			netpath = netpath[2:]
			netpath = Rules.Join.rewrite(netpath)
			self.cache.init( netpath )
			mainlog.info( '%s: Prepped cache, position: %s',
					self, self.cache.abspath() )

	def open_cache( self ):
		assert self.cache.path
		self.cache.open()
		self.cache.stat()

	def move( self ):
		mainlog.debug("Error: TODO: ProxyData.move")

	def set_broken( self ):
		mainlog.debug("Error: TODO: ProxyData.set_broken")

	def close(self):
		self.cache = None
		self.descriptor = None
		mainlog.debug("%s: closed ", self)

	def set_data(self, attribute, value):
		assert not getattr( self.descriptor, attribute ), attribute
		setattr( self.descriptor, attribute, value )

	def update_data(self):
# after server response headers
		if not self.descriptor.resource:
			self.descriptor.resource = Resource()
		resp_headers = self.protocol.args()
		mediatype = resp_headers.get( 'Content-Type', None )
		if not mediatype:
			resp_headers['Content-Type'] = 'application/octet-stream'
		self.map_to_data( HTTP.filter_entity_headers( resp_headers ) )
		self.descriptor.mediatype_auth = mediatype != None
		mainlog.debug( '%s: update_data %r ', self, self.descriptor )

# before client response headers
	def finish_data(self):
		assert self.descriptor.resource.url, self.descriptor.resource
		if self.descriptor.resource.url:
			self.descriptor.resource.commit()
		self.descriptor.commit()
		assert self.descriptor.id
# XXX
#		if not self.descriptor.id:
		mainlog.debug('%s finish_data %r %r ', self, self.descriptor, self.descriptor.resource )

	###

	header_data_map = {
#		'allow': (str,'resource.allow'),
		'content-length': (int, 'size'),
		'content-language': (str, 'language'),
#		'content-location': (str,'resource.location'),
# XXX:'content-md5': (str,'content.md5'),
		#'content-range': '',
		#'vary': 'vary',
#		'last-modified': (str, 'mtime'),
#		'expires': (str,'resource.expires'),
		'etag': (strstr,'etag'),
	}

	_attr_map = {
		'qs': (float, 'quality'),
		'charset': (str, 'charset'),
	}

	def map_to_data( self, headers=None ):
		if not headers:
			headers = self.protocol.args()

		headerdict = HeaderDict(headers)
		
		for hn, hv in headerdict.items():
			h = "set_%s" % hn.lower().replace('-','_')
			if hasattr( self, h ):
				getattr( self, h )(hv)
			elif hn.lower() in self.header_data_map:
				ht, hm = self.header_data_map[hn.lower()]
				if hm.startswith('resource.'):
					hm = hm.replace('resource.', '')
					setattr( self.descriptor.resource, hm, ht(hv) )
				else:
					setattr( self.descriptor, hm, ht(hv) )
			else:
				mainlog.warn("Unrecognized entity header %s", hn)

	def map_to_headers(self):
		headerdict = HeaderDict()
		if self.descriptor.size:
			headerdict.update({
				'Content-Length': self.descriptor.size,
			})
#		if self.descriptor.resource:
#			headerdict.update({
#				'Content-Location': self.descriptor.resource.url
#			})
		if self.descriptor.id: 
			assert self.cache.mtime > -1, "XXX"
		headerdict.update({
			'Last-Modified': self.get_last_modified(),
		})
		if self.descriptor.mediatype and self.descriptor.mediatype_auth:
			headerdict.update({
				'Content-Type': self.get_content_type(),
			})
		if self.descriptor.etag:
			headerdict.update({
				'ETag': '"%s"' % self.descriptor.etag,
			})
		return headerdict


	## Proxy lifecycle hooks

	def prepare_request( self, request ):
		"""
		Protocol is about to proxy the request, prepare the cache
		and descriptor instances, and return the updated headers.
		"""

		req_headers = request.headers

		mainlog.debug( "%s: Preparing for request to %s", self, self.protocol.url )

		self.init_data( self.protocol.url )

		if not self.descriptor.path:
			self.init_cache( self.protocol.url )
			abspath = self.cache.abspath()
			self.set_data( 'path', self.cache.path )
			self.set_data( 'mtime', time.time() )
			mainlog.debug( '%s: Prepared descriptor at %r', self, abspath )

		else:
			assert self.descriptor.exists()
			assert self.descriptor.id
			self.init_cache( )
			self.cache.path = self.descriptor.path.replace( Runtime.PARTIAL, '' )
			self.cache.stat()
			mainlog.debug( 'Existing descriptor at %r', self.descriptor.path )

		# Prepare proxied request headers
		via = "%s:%i" % (Runtime.HOSTNAME, Runtime.PORT)
		if req_headers.setdefault('Via', via) != via:
			req_headers['Via'] += ', '+ via
		# XXX: should it do something with encoding?
		req_headers.pop( 'Accept-Encoding', None )
		# TODO: RFC 2616 14.35.2 Range requests and partial content response
		htrange = req_headers.pop( 'Range', None )
		# TODO: RFC 2616 14.9.4: Cache revalidation and reload controls
		cache_control = req_headers.pop( 'Cache-Control', None )
		# TODO: Store relationship with 
		relationtype = req_headers.pop('X-Relationship', None)
		# XXX: anonymize, check with [RFC 2616 14.36]
		referer = req_headers.get('Referer', None)
		# FIXME: Client may have a cache too that needs to be
		# validated by the proxy.
		req_headers.pop( 'If-None-Match', None )
		req_headers.pop( 'If-Modified-Since', None )

		# Fill in from datastore if we have a local file
		if self.descriptor.exists():

			self.cache.stat()

			if ( self.cache.partial or self.cache.full ):
				mdtime = self.get_last_modified()

			if self.cache.partial:
				assert self.cache.size < self.descriptor.size, \
						( "Illegal state: file should have been completed", self.cache.size, self.descriptor.size )
				mainlog.note('Requesting resume of partial file in cache: '
						'%i bytes, %s', self.cache.size, mdtime )
				req_headers[ 'Range' ] = 'bytes=%i-' % ( self.cache.size,) # self.descriptor.size+1 )
				req_headers[ 'If-Range' ] = mdtime

			elif self.cache.full:
				mainlog.info( 'Checking complete file in cache: %s', mdtime )
				req_headers[ 'If-Modified-Since' ] = mdtime
				if self.descriptor.etag:
					req_headers[ 'If-None-Match' ] = '"%s"' % self.descriptor.etag
		

		return req_headers

	def finish_request( self ):
		"""
		Protocol has parsed then response headers and determined the appropiate 
		Response type.
		"""

		mainlog.info ("%s: Completing request phase", self)

		if not self.descriptor.id:

			# XXX: allow for opaque moves of descriptors
#			if self.cache.path != self.descriptor.path:
#				assert not ( self.cache.partial or self.cache.full )
#				path = self.descriptor.path
#				p = len(Runtime.ROOT)
#				assert path[:p] == Runtime.ROOT, "hmmm"
#				self.cache.path = path[p:].replace( Runtime.PARTIAL, '' )
			# /XXX

			# set new data
			self.update_data()
			#assert self.descriptor.etag

			res = Resource().find( Resource.url == self.protocol.url )
			if not res:
				if not self.descriptor.resource.url:
					self.descriptor.resource.url = self.protocol.url
		else:
			assert self.cache.path == self.descriptor.path, (
					self.cache.abspath(), self.descriptor, self.cache.path)

		self.open_cache()
		mainlog.info("%s: open_cache %s", self, self.cache.partial or
						self.cache.full)

	def prepare_response( self ):
		args = self.protocol.args()
		args.update(self.map_to_headers())
		mainlog.info ("%s: prepare_response %s", self, args)
		#assert 'Content-Length' in args and args['Content-Length'] > 0, dict(
		#		to_headers=self.map_to_headers(), 
		#		to_data=self.map_to_data(),
		#		size=self.protocol.size,
		#		protohdr=args,
		#	)
		via = "%s:%i" % (Runtime.HOSTNAME, Runtime.PORT)
		if args.setdefault('Via', via) != via:
			args['Via'] += ', '+ via
		args[ 'Connection' ] = 'close'
		return args

	def finish_response( self ):
		size = self.cache.tell()
		mainlog.info("%s: finish_response at cache.tell=%i", self, size)
		if not self.descriptor.size:
			mainlog.debug("%s Updated descriptor size from cache pointer %s", self, self.cache)
			self.descriptor.size = size
		if size == self.descriptor.size:
			self.cache.stat()
			if self.cache.partial:
				abspath = os.path.join( Runtime.ROOT, self.cache.path )
				assert abspath == self.cache.full_path()
				partial_path = self.cache.partial_path()
				assert os.path.exists( partial_path ), partial_path
				assert partial_path == Cache.suffix_ext( abspath, Runtime.PARTIAL )
				os.rename( partial_path, abspath )
				os.utime( abspath, ( self.descriptor.mtime, self.descriptor.mtime ) )
				mainlog.note("%s: Finalized %r at %i", self, abspath, size )
				self.descriptor.path = self.cache.path
				assert Runtime.PARTIAL not in self.descriptor.path
				self.descriptor.commit()
		else:
			mainlog.debug("Descriptor does not match: %s", self.descriptor.size)
			mainlog.note("%s: Closed partial %r at %s bytes", self, self.descriptor.path, size )
			self.descriptor.path = Cache.suffix_ext( self.cache.path, Runtime.PARTIAL )
			os.utime( os.path.join( Runtime.ROOT,  self.descriptor.path ), ( self.descriptor.mtime, self.descriptor.mtime ) )
			assert Runtime.PARTIAL in self.descriptor.path
			assert not self.descriptor.path.startswith(Runtime.ROOT), self.descriptor.path
			self.descriptor.commit()

		#print self, 'finish_response, tell=%i, meta.size=%i, file.size=%i, meta.mtime=%s, file.mtime=%s' % (
		#				size, self.descriptor.size, self.cache.size,\
		#				self.descriptor.mtime, self.cache.mtime )
		#self.cache.close()
		#path = self.descriptor.path
		#url = self.get_content_location()
		self.finish_data()
		#self.close()
		mainlog.info("ProxyData.finish_response is done. ")
		return
# XXX
		complete = '/tmp/htcache-systemtest3.cache/www.w3.org/Protocols/HTTP/1.1/rfc2616bis/draft-lafon-rfc2616bis-03.txt'
		while not os.path.exists( complete ):
			mainlog.crit("NO STAT %s", complete)
			time.sleep(1)
		mainlog.info("STAT %s", os.stat(complete))

# XXX
#		if url:
#			print url, Resource().find( Resource.url == url )
#		print path, Descriptor().find( Descriptor.path == path )
	def prepare_static(self):
		"""
		Set cache location and open any partial or complete file, 
		then fetch descriptor if it exists. 

		XXX: Even when the current download is still running, this needs to have the
		descriptor already.
		"""
		self.init_data( self.protocol.url )
		self.init_cache( )
		if not self.descriptor.id:
			return False

		self.cache.path = self.descriptor.path.replace( Runtime.PARTIAL, '' )
		self.cache.stat()
		assert self.cache.full,\
				"Nothing there to open: no content. "
		self.open_cache()
		#assert self.data.is_open() and self.cache.full(), \
		#	"XXX: sanity check, cannot have partial served content, serve error instead"
		return True

	def __str__(self):
		return "[ProxyData %s]" % hex(id(self))

### Descriptor Storage types:

SqlBase = declarative_base()


class SessionMixin(object):

	"""
	"""

	sessions = {}

	@staticmethod
	def get_instance(name='default', dbref=None, init=False, read_only=False):
		# XXX: read_only
		if name not in SessionMixin.sessions:
			assert dbref, "session does not exists: %s" % name
			session = get_session(dbref, init)
			#assert session.engine, "new session has no engine"
			SessionMixin.sessions[name] = session
		else:
			session = SessionMixin.sessions[name]
			#assert session.engine, "existing session does not have engine"
		return session

	@staticmethod
	def close_instance(name='default', dbref=None, init=False, read_only=False):
		if name in SessionMixin.sessions:
			session = SessionMixin.sessions[name]
		session.close()

	# XXX: SessionMixin.key_names
	key_names = []

#	def __nonzero__(self):
#		return self.id != None
#
	def key(self):
		key = {}
		for a in self.key_names:
			key[a] = getattr(self, a)
		return key

	def commit(self):
		session = SessionMixin.get_instance()
		session.add(self)
		session.commit()

	def find(self, *args):
		try:
			return self.fetch(*args)
		except NoResultFound, e:
			mainlog.info( "%s find: No results for %r", self, args )

	def fetch(self, *args):
		"""
		Keydict must be filter parameters that return exactly one record.
		"""
		session = SessionMixin.get_instance()
		return session.query(self.__class__).filter(*args).one()

	def exists(self):
		return self.id != None
		return self.fetch() != None 

	def __repr__(self):
		return self.__str__()


class Resource(SqlBase, SessionMixin):
	"""
	"""
	__tablename__ = 'resources'
	id = Column(Integer, primary_key=True)
	url = Column(String(255), nullable=False)
#	host = Column(String(255), nullable=False)
#	path = Column(String(255), nullable=False)
#	key_names = [id]
	
	def __str__(self):
		return "Resource(%s)" % pformat(dict(
			id=self.id,
			url=self.url,
		))


class Descriptor(SqlBase, SessionMixin):
	"""
	"""
	__tablename__ = 'descriptors'

	id = Column(Integer, primary_key=True)
	resource_id = Column(Integer, ForeignKey(Resource.id), nullable=False)
	resource = relationship( Resource, 
#			primaryjoin=resource_id==Resource.id, 
			backref='descriptors')
	path = Column(String(255), nullable=True)
	mediatype = Column(String(255), nullable=False)
	mediatype_auth = Column(Boolean, nullable=False)
	charset = Column(String(255), nullable=True)
	language = Column(String(255), nullable=True)
	size = Column(Integer, nullable=True)
	mtime = Column(Integer, nullable=False)
	quality = Column(Float, nullable=True)
	etag = Column(String(255), nullable=True)
#	key_names = [id]

	def __str__(self):
		return "Descriptor(%s)" % pformat(dict(
			id=self.id,
			resource_id=self.resource_id,
			path=self.path,
			etag=self.etag,
			size=self.size,
			charset=self.charset,
			language=self.language,
			quality=self.quality,
			mtime=self.mtime,
			mediatype=self.mediatype
		))

	@staticmethod
	def find_latest( url ):
		descriptor = get_backend().query(Descriptor)\
			.join("resource").filter(
				Resource.url == url
			).order_by(
				Descriptor.mtime 
			).first()
		return descriptor


class Relation(SqlBase, SessionMixin):
	"""
	"""
	__tablename__ = 'relations'
	id = Column(Integer, primary_key=True)
	relate = Column(String(16), nullable=False)
	revuri = Column(Integer, ForeignKey(Resource.id), nullable=False)
	reluri = Column(Integer, ForeignKey(Resource.id), nullable=False)
#	key_names = [id]

	def __str__(self):
		return "Relation(%s)" % pformat(dict(
			id=self.id,
			relate=self.relate,
			revuri=self.revuri,
			reluri=self.reluri
		))



#/FIXME

_backends = {}

def get_backend(name='default', read_only=False):
	if name in _backends:
		backend = _backends[name]
	else:
		backend = SessionMixin.get_instance(
				name='default', 
				dbref=Runtime.DATA, 
				init=True,
				read_only=read_only)
		_backends[name] = backend
	return backend

def get_session(dbref, initialize=False):
	engine = create_engine(dbref)#, encoding='utf8')
	#engine.raw_connection().connection.text_factory = unicode
	if initialize:
		mainlog.debug("Applying SQL DDL to DB %s ", dbref)
		SqlBase.metadata.create_all(engine) # issue DDL create 
		mainlog.info("Updated data schema")
	session = sessionmaker(bind=engine)()
	return session


###


# Query commands 

def print_records():
	rs = get_backend().query(Resource).all()
	for res in rs:
		print res
		for d in res.descriptors:
			print '\t', str(d).replace('\n', '\n\t')

def print_record(url):
	get_backend()
	res = Resource().fetch(Resource.url == url)
	print res
	for d in res.descriptors:
		print '\t', str(d).replace('\n', '\n\t')

def list_locations():
	backend = get_backend()
	for res in backend.query(Resource).all():
		for d in res.descriptors:
			print d.path
	backend.close()

def list_urls():
	backend = get_backend()
	for url in backend.resources:
		res = backend.find(url)
		print res.url

def print_location(url):
	backend = get_backend()
	netpath = url[5:]
	res = Resource().fetch(Resource.url == netpath)
	for d in res.descriptors:
		print d.path


# TODO: find_records by attribute query
def find_records(q):
	import sys
	backend = get_backend()
	print 'Searching for', q

	attrpath, valuepattern = q.split(':')

	for path in backend:
		res = backend[path]
		urls, mime, qs, n, meta, feats = res
		for u in urls:
			if q in u:
				print path, mime, urls
#		for k in props:
#			if k in ('0','srcref'):
#				if props[k] in res[0]:
#					print path
#			elif k in ('1','mediatype'):
#				if props[k] == res[1]:
#					print path
#			elif k in ('2','charset'):
#				if props[k] == res[2]:
#					print path
#			elif k in ('3','language'):
#				if props[k] in res[3]:
#					print path
#			elif k in ('4','feature'):
#				for k2 in props[k]:
#					if k2 not in res[4]:
#						continue
#					if res[4][k2] == props[k][k2]:
#						print path
	backend.close()
	mainlog.debug("End of findinfo")


# TODO: integrate with other print_info
def print_info(*paths):
	backend = get_backend()
	import sys
	recordcnt = 0
	for path in paths:
		if not path.startswith(os.sep):
			path = Params.ROOT + path
#		path = path.replace(Params.ROOT, '')
		if path not in backend:
			mainlog.debug("Unknown cache location: %s", path)
		else:
			print path, backend.find(path)
			recordcnt += 1
	if recordcnt > 1:
		print >>sys.stderr, "Found %i records for %i paths" % (recordcnt,len(paths))
	elif recordcnt == 1:
		print >>sys.stderr, "Found one record"
	else:
		print >>sys.stderr, "No record found"
	backend.close()


def print_media_list(*media):
	"document, application, image, audio or video (or combination)"
	backend = get_backend()
	for m in media:
		# TODO: documents
		if m == 'image':
			for path in backend:
				res = backend[path]
				if 'image' in res[1]:
					print path
		if m == 'audio':
			for path in backend:
				res = backend[path]
				if 'audio' in res[1]:
					print path
		if m == 'videos':
			for path in backend:
				res = backend[path]
				if 'video' in res[1]:
					print path

def check_data(cache, uripathnames, mediatype, d1, d2, meta, features):
	"""
	References in descriptor cache must exist as file.
	This checks existence and the size property, if complete.

	All rules should be applied.
	"""
	if not Params.LOG_LEVEL:
		Params.LOG_LEVEL = 1
	pathname = cache.path
	if cache.partial:
		pathname += '.incomplete'
	if not (cache.partial or cache.full):
		mainlog.info("Missing %s" % pathname)
		return
	if 'Content-Length' not in meta:
		mainlog.info("Missing content length of %s" % pathname)
		return
	length = int(meta['Content-Length'])
	if cache.full() and os.path.getsize(pathname) != length:
		mainlog.err("Corrupt file: %s, size should be %s" % (pathname, length))
		return
	return True

def validate_cache(pathname, uripathnames, mediatype, d1, d2, meta, features):
	"""
	Descriptor properties must match those of file.
	This recalculates the files checksum.
	"""
	return True

def check_tree(pathname, uripathnames, mediatype, d1, d2, meta, features):
	return True

def get_cache(hostinfo, path):
	"""
	XXX: rewrite path to cache location, ie. instantiate Cache object and
	return. All location rewriting should be handled here? or use database instead..
	"""
	assert False, ("TODO: write get_cache method", hostinfo, path)

def check_files():
	backend = SessionMixin.get_instance(True)
# XXX old
	#if Params.PRUNE:
	#	descriptors = SessionMixin.get_instance()
	#else:
	#	descriptors = SessionMixin.get_instance(main=False)
	pcount, rcount = 0, 0
	mainlog.info("Iterating paths in cache root location. ")

	for root, dirs, files in os.walk(Params.ROOT):

		# Ignore files in root
		if not root[len(Params.ROOT):]:
			continue

#		rdir = os.path.join(Params.ROOT, root)
		for f in dirs + files:
			f = os.path.join(root, f)
			#if path_ignore(f):
			#	continue
			pcount += 1
			if f not in backend.descriptors:
				if os.path.isfile(f):
					mainlog.warn("Missing descriptor for %s" % f)
					if Runtime.PRUNE:
						size = os.path.getsize(f)
						if size < Runtime.MAX_SIZE_PRUNE:
							os.unlink(f)
							mainlog.warn("Removed unknown file %s" % f)
						else:
							mainlog.note("Keeping %sMB" % (size / (1024 ** 2)))#, f))
				elif not (os.path.isdir(f) or os.path.islink(f)):
					mainlog.warn("Unrecognized path %s" % f)
			elif f in backend.descriptors:
				rcount += 1
				descr = backend.descriptors[f]
				assert isinstance(descr, Record)
				uriref = descr[0][0]
				mainlog.info("Found resource %s" % uriref, threshold=1)
# XXX: hardcoded paths.. replace once Cache/Resource is properly implemented
				port = 80
				if len(descr[0]) != 1:
					mainlog.note("Multiple references %s" % f)
					continue
				urlparts = urlparse.urlparse(uriref)
				hostname = urlparts.netloc
				pathname = urlparts.path[1:]
# XXX: cannot reconstruct--, or should always normalize?
				if urlparts.query:
					#print urlparts
					pathname += '?'+urlparts.query
				hostinfo = hostname, port
				cache = get_cache(hostinfo, pathname)
				#print 'got cache', cache.getsize(), cache.path
# end
	mainlog.note("Finished checking %s cache locations, found %s resources" % (
		pcount, rcount))
	backend.close()

def check_cache():
	#term = Resource.TerminalController()
	#print term.render('${YELLOW}Warning:${NORMAL}'), 'paper is crinkled'
	#pb = Resource.ProgressBar(term, 'Iterating descriptors')
#	if Params.PRUNE:
#		descriptors = SessionMixin.get_instance()
#	else:
#		descriptors = SessionMixin.get_instance(main=False)
	backend = SessionMixin.get_instance(True)

	refs = backend.descriptors.keys()
	count = len(refs)
	log("Iterating %s descriptors" % count)
	for i, ref in enumerate(refs):
		mainlog.debug("%i, %s" % (i, ref))
		descr = backend.descriptors[ref]
		log("Record data: [%s] %r" %(ref, descr.data,), 2)
		urirefs, mediatype, d1, d2, meta, features = descr
		#progress = float(i)/count
		#pb.update(progress, ref)
# XXX: hardcoded paths.. replace once Cache/Resource is properly implemented
		port = 80
		if len(urirefs) != 1:
			log("Multiple references %s" % ref)
			continue
		urlparts = urlparse.urlparse(urirefs[0])
		hostname = urlparts.netloc
		pathname = urlparts.path[1:]
# XXX: cannot reconstruct--, or should always normalize?
		if urlparts.query:
			#print urlparts
			pathname += '?'+urlparts.query
		hostinfo = hostname, port
		cache = get_cache(hostinfo, pathname)
# end
		act = None
		if not check_data(cache, *descr):
			if not Params.PRUNE:
				continue
			act = True
			if cache.full() or cache.partial():
				path = cache.path
				if cache.partial():
					path += '.incomplete'
				if os.path.getsize(path) > Params.MAX_SIZE_PRUNE:
					if Params.INTERACTIVE:
						pass
					log("Keeping %s" % path)
					continue
				if os.path.isfile(path):
					print 'size=', cache.getsize() / 1024**2
					os.unlink(path)
					log("Deleted %s" % path)
				else:
					log("Unable to remove dir %s" % path)
			del backend.descriptors[ref]
			log("Removed %s" % cache.path)
	log("Finished checking %s cache descriptors" % count)
	backend.close()
	#pb.clear()


