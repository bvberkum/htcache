import hashlib, socket, time, traceback, urlparse, urllib

import fiber
import Params, Resource, Rules, HTTP, Runtime
from util import json_write, json_read
import log

mainlog =  log.get_log('main')

class BlindResponse:

	"""
	Like BlindProtocol, BlindResponse tries for graceful
	recovery in unexpected protocol situations.
	"""

	Done = False

	def __init__( self, protocol, request ):

		if hasattr(protocol, 'responsebuf'):
			self.__sendbuf = protocol.responsebuf()
		else:
			self.__sendbuf = protocol.recvbuf()

	def hasdata( self ):

		return bool( self.__sendbuf )

	def send( self, sock ):

		assert not self.Done
		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]

	def needwait( self ):

		return False

	def recv( self, sock ):

		assert not self.Done
		chunk = sock.recv( Params.MAXCHUNK )
		if chunk:
			self.__sendbuf += chunk
		elif not self.__sendbuf:
			self.Done = True

	def finalize(self, client):
		pass


class ProxyResponse(BlindResponse):

	pass


class DataResponse:

	Done = False
	content_rewrite = []

	def __init__( self, protocol, request ):

		self.__protocol = protocol
		self.__pos, self.__end = request.range()

		mainlog.debug("New %s for %s", self, request)

		#assert protocol._HttpProtocol__status in (200, 206),\
		#	protocol._HttpProtocol__status
		args = protocol.data.prepare_response()

		assert protocol.data.cache
		assert protocol.data.descriptor.mediatype

		if self.__end == -1 and protocol.data.descriptor.size:
			self.__end = protocol.data.descriptor.size
		#assert 'Content-Length' in args

		# TODO: on/off:
		#if protocol.capture:
		#	self.__hash = hashlib.sha1()

# XXX: this may need to be on js serving..
#		if self.__protocol.rewrite:
#			args['Access-Control-Allow-Origin'] = "%s:%i" % request.hostinfo

		assert 'Last-Modified' in args
		assert 'Content-Type' in args

		if self.__pos == 0 and self.__end in ( -1, self.__protocol.size ):
			head = 'HTTP/1.1 200 OK'

		elif self.__end >= 0:
			head = 'HTTP/1.1 206 Partial Content'
			args[ 'Content-Length' ] = str( self.__end - self.__pos )
			if self.__protocol.size >= 0:
				args[ 'Content-Range' ] = 'bytes %i-%i/%i' % (
						self.__pos, self.__end - 1, self.__protocol.size )
			else:
				args[ 'Content-Range' ] = 'bytes %i-%i/*' % (
						self.__pos, self.__end - 1 )

		elif self.__end != -1:
			head = 'HTTP/1.1 416 Requested Range Not Satisfiable'
			args[ 'Content-Range' ] = 'bytes */*'
			args[ 'Content-Length' ] = '0'

		else:
			assert False, dict( request=( self.__pos, self.__end ), proto=(
				protocol.tell(), protocol.size ), size=protocol.data.descriptor.size )

		mainlog.note('HTCache responds %r', head.strip())

		if Runtime.LOG_LEVEL == log.DEBUG:
			for key in args:
				if not args[key]:
					mainlog.err("Error: no value %s" % key)
					continue
				mainlog.debug('> %s: %s' % ( key, args[ key ] )) #.replace( '\r\n', ' > ' ) ),

		# Prepare response for client
		self.__sendbuf = '\r\n'.join( [ head ] +
				map( ': '.join, map( lambda x:(x[0],str(x[1])), args.items() )) + [ '', '' ] )
		if Runtime.LIMIT:
			self.__nextrecv = 0

	def hasdata( self ):

		if self.__sendbuf:
			return True
		elif self.__pos >= self.__protocol.tell():
#			mainlog.debug("[%s hasdata (%s >= %s) ]", self, self.__pos, self.__protocol.tell())
			return False
		elif self.__pos < self.__end or self.__end == -1:
#			mainlog.debug
#					("[%s hasdata (%s < %s or %s == -1) ]", self, self.__pos, self.__end, self.__end)
			return True
		else:
			assert self.__end != None
			return False

	def send( self, sock ):

		assert not self.Done
		if self.__sendbuf:
			bytecnt = sock.send( self.__sendbuf )
			self.__sendbuf = self.__sendbuf[ bytecnt: ]
		else:
			bytecnt = Params.MAXCHUNK
			if 0 <= self.__end < self.__pos + bytecnt:
				bytecnt = self.__end - self.__pos

			chunk = self.__protocol.read( self.__pos, bytecnt )
			if self.__protocol.rewrite:
				delta, chunk = Rules.Rewrite.run(chunk)
				self.__protocol.size += delta
			try:
				self.__pos += sock.send( chunk )
			except Exception, e:
				mainlog.err("Client aborted: %s", e)
				self.Done = True
				#XXX:if not self.__protocol.cache.full():
				#	self.__protocol.cache.remove_partial()
				return
		self.Done = not self.__sendbuf and (
				self.__pos >= self.__protocol.size >= 0
				or self.__pos >= self.__end >= 0 )

		# TODO: store hash for new recv'd content
		#if self.__protocol.capture and self.Done:
		#	print 'hash', self.__hash.hexdigest()

	def needwait( self ):

		return Runtime.LIMIT and max( self.__nextrecv - time.time(), 0 )

	def recv( self, sock ):
		"""
		Read chuck from server response. Hash or rewrite if needed.
		"""

		assert not self.Done
		chunk = sock.recv( Params.MAXCHUNK )
		if chunk:
			self.__protocol.write( chunk )
			#if self.__protocol.capture:
			#	self.__hash.update( chunk )
			if Runtime.LIMIT:
				self.__nextrecv = time.time() + len( chunk ) / Runtime.LIMIT
		else:
			if self.__protocol.size >= 0:
				if self.__protocol.size != self.__protocol.tell():
					mainlog.err('connection closed prematurely')
					
			else:
				self.__protocol.size = self.__protocol.tell()
				mainlog.debug('Connection closed at byte %i', self.__protocol.size)
			self.Done = not self.hasdata()

		#if self.Done:
		#	for pattern, substitute in self.content_rewrite:
		#		self.__protocol.write( substitute )
				#chunk, count = pattern.subn(substitute, chunk)
				#self.size += len(substitute)
				#(count * len(substitute))
				#log("Rewritten content with %r, %i times" % (
				#		(pattern, substitute), count))

	def finalize(self, client):
		mainlog.debug('%s: finalizing %s' % (self, self.__protocol.tell()))
		self.__protocol.finish()

	def __str__(self):
		if self.__end:
			return "[DataResponse %s cache=%s/%s, req=%s/%s]" % (
					hex(id(self)),
					self.__protocol.tell(), self.__protocol.size,
					self.__pos, self.__end)
		else:
			return "[DataResponse %s cache=%s/%s]" % (
					hex(id(self)),
					self.__protocol.tell(),
					self.__protocol.size)


class ChunkedDataResponse( DataResponse ):

	def __init__( self, protocol, request ):
		DataResponse.__init__( self, protocol, request )
		self.__protocol = protocol
		self.__recvbuf = ''

	def recv( self, sock ):
		assert not self.Done
		chunk = sock.recv( Params.MAXCHUNK )
		assert chunk, 'chunked data error: connection closed prematurely'
		self.__recvbuf += chunk
		while '\r\n' in self.__recvbuf:
			head, tail = self.__recvbuf.split( '\r\n', 1 )
			chunksize = int( head.split( ';' )[ 0 ], 16 )
			if chunksize == 0:
				self.__protocol.size = self.__protocol.tell()
				mainlog.debug('Connection closed at byte %i', self.__protocol.size)
				self.Done = not self.hasdata()
				return
			if len( tail ) < chunksize + 2:
				mainlog.debug('Waiting for chunk end')
				return
			assert tail[ chunksize:chunksize+2 ] == '\r\n', \
					'chunked data error: chunk does not match announced size'
			mainlog.debug('Received %i byte chunk', chunksize)
			self.__protocol.write( tail[ :chunksize ] )
			self.__recvbuf = tail[ chunksize+2: ]
		mainlog.debug('Received %i byte in chunks', len(self.__recvbuf))
		#protocol.data.close()

	def __str__(self):
		return "[ChunkedDataResponse %s]" % hex(id(self))


class BlockedContentResponse:

	Done = False

	def __init__(self, status, request):
		url = request.hostinfo + (request.envelope[1],)
		self.__sendbuf = "HTTP/1.1 403 Dropped By Proxy\r\n'\
				'Content-Type: text/html\r\n\r\n"\
				+ open(Params.HTML_PLACEHOLDER).read() % {
						'host': Runtime.HOSTNAME,
						'port': Runtime.PORT,
						'location': '%s:%i/%s' % url,
						'software': 'htcache/%s' % Params.VERSION }

	def hasdata( self ):
		return bool( self.__sendbuf )

	def send( self, sock ):
		assert not self.Done
		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]
		if not self.__sendbuf:
			self.Done = True

	def needwait( self ):
		return False

	def recv( self ):
		raise AssertionError

	def finalize(self, client):
		pass

	def __str__(self):
		return "[BlockedContentResponse %s]" % hex(id(self))


class BlockedImageContentResponse:

	Done = False

	def __init__(self, status, request):
		data = open(Params.IMG_PLACEHOLDER).read()
		self.__sendbuf = 'HTTP/1.1 403 Dropped By Proxy\r\n'\
				'Content-Length: %i\r\n'\
				'Content-Type: image/png\r\n\r\n%s' % (
				len(data), data)

	def hasdata( self ):
		return bool( self.__sendbuf )

	def send( self, sock ):
		assert not self.Done
		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]
		if not self.__sendbuf:
			self.Done = True

	def needwait( self ):
		return False

	def recv( self ):
		raise AssertionError

	def finalize(self, client):
		pass

	def __str__(self):
		return "[BlockedImageContentResponse %s]" % hex(id(self))


class DirectResponse:

	Done = False

	"""
	HTCache generated response for request directly to
	proxy port.
	"""

	urlmap = {
		'control': 'control_proxy',
		'reload': 'reload_proxy',
		'dhtml.css': 'serve_stylesheet',
		'dhtml.js': 'serve_script',
		'echo': 'serve_echo',
		'page-info': 'serve_descriptor',
		'info': 'serve_params',
		'browse': 'serve_frame',
		'downloads': 'serve_downloads',
		'list': 'serve_list',
	}

	def __init__( self, protocol, request, status='200 Okeydokey, here it comes', path=None):
		if status[0] == '2':
			path = protocol.reqname
			if '?' in path:
				path = path.split('?')[0]
			if path not in self.urlmap:
				status = '404 No such resource'
				path = 'echo'
		else:
			path = 'echo'
		self.action = self.urlmap[path]
		getattr(self, self.action)(status, protocol, request)

	def serve_list(self, status, protocol, request):
		self.prepare_response(
				"200 OK",
				"# Downloads \n"
				"" + ('\n'.join(map(str,Runtime.DOWNLOADS.keys())))
			)

	def serve_downloads(self, status, protocol, request):
		self.prepare_response(
				"200 OK",
				"No data for %r %r %r %r"%request.url
			)

	def serve_echo(self, status, protocol, request):
		lines = [ 'HTCache: %s' % status, '' ]

		lines.append( 'Request echo ing:' )
		lines.append( '' )

		head, body = request.recvbuf().split( '\r\n\r\n', 1 )
		for line in head.splitlines():
			lines.append( len( line ) > 78 and '  %s...' %
					line[ :75 ] or '  %s' % line )
		if body:
			lines.append( '+ Body: %i bytes' % len( body ) )

		lines.append( '' )
		if protocol and protocol.has_response():
			lines.append( '(Partial) Response:' )
			lines.append( '' )
			head, body = protocol.recvbuf().split( '\r\n\r\n', 1 )
			for line in head.splitlines():
				lines.append( len( line ) > 78 and '  %s...' %
						line[ :75 ] or '  %s' % line )
			lines.append( '' )

		lines.append( traceback.format_exc() )

		self.__sendbuf = "HTTP/1.1 %s\r\n"\
			"Access-Control-Allow-Origin: *\r\n"\
			"Content-Type: text/plain\r\n"\
			"\r\n%s" % ( status, '\n'.join( lines ) )

	def control_proxy(self, status, protocol, request):
		head, body = request.recvbuf().split( '\r\n\r\n', 1 )
		req = {
				'args': request.headers
			}
		if body:
			try:
				req = json_read(body)
			except:
				#print "JSON: ",request.recvbuf()
				raise
		# TODO: echos only
		self.prepare_response(status,
				json_write(req), mime="application/json")

	def reload_proxy(self, status, protocol, request):
		self.prepare_response(status, "Reloading gateway")

	def serve_stylesheet(self, status, protocol, request):
		cssdata = open(Params.PROXY_INJECT_CSS).read()
		self.__sendbuf = "\r\n".join( [
			"HTTP/1.1 %s" % status,
			"Content-Type: text/css\r\n",
			cssdata
		])

	def serve_frame(self, status, protocol, request):
		status = '200 Have A Look'
		host = "%s:%s" % request.hostinfo
		uri = '?'.join(request.envelope[1].split('?')[1:])
		lines = [
			'<html>',
			'<head><title>HTCache browser</title>',
			'<link rel="stylesheet" type="text/css" href="http://'+host+'/htcache.css" />',
			'</head>',
			'<body id="htcache-browse">',
			'<pre>',
			'</pre>',
			'<iframe src="'+uri+'" />',
			'</body>',
			'</html>']

		self.__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/html\r\n'\
				'\r\n%s' % ( status, '\n'.join( lines ) )

	def serve_params(self, status, protocol, request):
		msg = Command.print_info(True)
		self.prepare_response(status, msg, mime='application/json')

	def serve_descriptor(self, status, protocol, request):
		q = urlparse.urlparse( request.url[3] )[4]
		url = urlparse.urlparse(urllib.unquote(q[4:]))
		# Translate URL to cache location
		if ':' in url[1]:
			hostinfo = url[1].split(':')
			hostinfo[1] = int(hostinfo[1])
		else:
			hostinfo = url[1], 80
		cache = Resource.get_cache(hostinfo, url[2][1:])
		# Find and print descriptor
		descriptors = Resource.get_backend()
		if cache.path in descriptors:
			descr = descriptors[cache.path]
			self.prepare_response(status,
					json_write(descr),
					mime='application/json')
		else:
			self.prepare_response("404 No Data", "No data for %s %s %s %s"%request.url)

	def serve_script(self, status, protocol, request):
		jsdata = open(Params.PROXY_INJECT_JS).read()
		self.__sendbuf = "\r\n".join( [
			"HTTP/1.1 %s" % status,
			"Content-Type: application/javascript\r\n"
			"Access-Control-Allow-Origin: *\r\n",
			jsdata
		])

	def prepare_response(self, status, msg, mime='text/plain'):
		if isinstance(msg, list):
			lines = msg
		else:
			lines = [msg]
		headers = "Access-Control-Allow-Origin: *\r\nContent-Type: "+mime+"\r\n"
		self.__sendbuf = 'HTTP/1.1 %s\r\n%s'\
				'\r\n%s' % ( status, headers, '\n'.join( lines ) )

	def hasdata( self ):
		return bool( self.__sendbuf )

	def send( self, sock ):
		assert not self.Done
		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]
		if not self.__sendbuf:
			self.Done = True

	def finalize(self, client):
		if self.action == 'reload_proxy':
			client.close()
			raise fiber.Restart()

	def needwait( self ):
		return False

	def recv( self ):
		raise AssertionError

	def __str__(self):
		return "[DirectResponse %s]" % hex(id(self))


class NotFoundResponse( DirectResponse ):

	def __init__( self, protocol, request ):
		if request.url()[0] == 'ftp':
			DirectResponse.__init__( self,
					protocol, request,
					status='550 Not Found'
				)
		elif request.url()[0] == 'http':
			DirectResponse.__init__( self,
					protocol, request,
					status='404 Not Found'
				)

	def __str__(self):
		return "[NotFoundResponse %s]" % hex(id(self))


class ExceptionResponse( DirectResponse ):

	def __init__( self, protocol, request ):
		traceback.print_exc()
		DirectResponse.__init__( self,
				protocol, request,
				status='500 Internal Server Error'
			)

	def __str__(self):
		return "[ExceptionResponse %s]" % hex(id(self))


