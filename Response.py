import Params, time, traceback


class BlindResponse:

	"""
	Like BlindProtocol, BlindResponse tries for graceful
	recovery in unexpected protocol situations.
	"""

	Done = False

	def __init__( self, protocol, request ):

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


class DataResponse:

	Done = False

	def __init__( self, protocol, request ):

		self.__protocol = protocol
		self.__pos, self.__end = request.range()
		if self.__end == -1:
			self.__end = self.__protocol.size

		try:
			args = self.__protocol.args()
		except:
			args = {}
		args[ 'Connection' ] = 'close'
		args[ 'Date' ] = time.strftime( Params.TIMEFMT, time.gmtime() )
		if self.__protocol.mtime >= 0:
			args[ 'Last-Modified' ] = time.strftime( Params.TIMEFMT, time.gmtime( self.__protocol.mtime ) )
		if self.__pos == 0 and self.__end == self.__protocol.size:
			head = 'HTTP/1.1 200 OK'
			if self.__protocol.size >= 0:
				args[ 'Content-Length' ] = str( self.__protocol.size )
		elif self.__end >= 0:
			head = 'HTTP/1.1 206 Partial Content'
			args[ 'Content-Length' ] = str( self.__end - self.__pos )
			if self.__protocol.size >= 0:
				args[ 'Content-Range' ] = 'bytes %i-%i/%i' % ( self.__pos, self.__end - 1, self.__protocol.size )
			else:
				args[ 'Content-Range' ] = 'bytes %i-%i/*' % ( self.__pos, self.__end - 1 )
		else:
			head = 'HTTP/1.1 416 Requested Range Not Satisfiable'
			args[ 'Content-Range' ] = 'bytes */*'
			args[ 'Content-Length' ] = '0'

		print 'Replicator responds', head
		if Params.VERBOSE > 1:
			for key in args:
				print '> %s: %s' % ( key, args[ key ].replace( '\r\n', ' > ' ) )

		self.__sendbuf = '\r\n'.join( [ head ] + map( ': '.join, args.items() ) + [ '', '' ] )
		if Params.LIMIT:
			self.__nextrecv = 0

	def hasdata( self ):

		if self.__sendbuf:
			return True
		elif self.__pos >= self.__protocol.tell():
			return False
		elif self.__pos < self.__end or self.__end == -1:
			return True
		else:
			return False

	def send( self, sock ):

		assert not self.Done
		if self.__sendbuf:
			bytes = sock.send( self.__sendbuf )
			self.__sendbuf = self.__sendbuf[ bytes: ]
		else:
			bytes = Params.MAXCHUNK
			if 0 <= self.__end < self.__pos + bytes:
				bytes = self.__end - self.__pos
			chunk = self.__protocol.read( self.__pos, bytes )
			self.__pos += sock.send( chunk )
		self.Done = not self.__sendbuf and ( self.__pos >= self.__protocol.size >= 0 or self.__pos >= self.__end >= 0 )

	def needwait( self ):

		return Params.LIMIT and max( self.__nextrecv - time.time(), 0 )

	def recv( self, sock ):

		assert not self.Done
		chunk = sock.recv( Params.MAXCHUNK )
		if chunk:
			self.__protocol.write( chunk )
			if Params.LIMIT:
				self.__nextrecv = time.time() + len( chunk ) / Params.LIMIT
		else:
			if self.__protocol.size >= 0:
				assert self.__protocol.size == self.__protocol.tell(), 'connection closed prematurely'
			else:
				self.__protocol.size = self.__protocol.tell()
				print 'Connection closed at byte', self.__protocol.size
			self.Done = not self.hasdata()


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
				print 'Connection closed at byte', self.__protocol.size
				self.Done = not self.hasdata()
				return
			if len( tail ) < chunksize + 2:
				return
			assert tail[ chunksize:chunksize+2 ] == '\r\n', 'chunked data error: chunk does not match announced size'
			if Params.VERBOSE > 1:
				print 'Received', chunksize, 'byte chunk'
			self.__protocol.write( tail[ :chunksize ] )
			self.__recvbuf = tail[ chunksize+2: ]


class BlockedContentResponse:

	Done = False

	def __init__(self, status, request):
		self.__sendbuf = "HTTP/1.1 403 Dropped By Proxy\r\n'\
				'Content-Type: text/html\r\n\r\n"\
				+ open(Params.HTML_PLACEHOLDER).read() % {
						'host': Params.HOSTNAME,
						'port': Params.PORT,
						'location': '%s:%i/%s' % request.url(),
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

	def __init__( self, status, request ):

		lines = [ 'HTTP Replicator: %s' % status, '', 'Requesting:' ]
		head, body = request.recvbuf().split( '\r\n\r\n', 1 )
		for line in head.splitlines():
			lines.append( len( line ) > 78 and '	%s...' % line[ :75 ] or '	%s' % line )
		if body:
			lines.append( '+ Body: %i bytes' % len( body ) )
		lines.append( '' )
		lines.append( traceback.format_exc() )

		self.__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/plain\r\n\r\n%s' % ( status, '\n'.join( lines ) )

	def hasdata( self ):

		return bool( self.__sendbuf )

	def send( self, sock ):

		assert not self.Done
		bytes = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytes: ]
		if not self.__sendbuf:
			self.Done = True

	def needwait( self ):

		return False

	def recv( self ):

		raise AssertionError



class ProxyResponse(DirectResponse):

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
		DirectResponse.__init__(self)
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
		mainlog.debug('ProxyResponse init: %s, %s', path, self)

	def serve_list(self, status, protocol, request):
		self.prepare_buffer(
				"200 OK",
				"# Downloads \n"
				"" + ('\n'.join(map(str,Params.DOWNLOADS.keys())))
			)

	def serve_downloads(self, status, protocol, request):
		assert isinstance(request.url, basestring), request.url
		self.prepare_buffer(
				"200 OK",
				"No data for %r "%request.url
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

		self._DirectResponse__sendbuf = "HTTP/1.1 %s\r\n"\
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
		self.prepare_buffer(status,
				json_write(req), mime="application/json")

	def reload_proxy(self, status, protocol, request):
		self.prepare_buffer(status, "Reloading gateway")

	def serve_stylesheet(self, status, protocol, request):
		cssdata = open(Params.PROXY_INJECT_CSS).read()
		self._DirectResponse__sendbuf = "\r\n".join( [
			"HTTP/1.1 %s" % status,
			"Content-Type: text/css\r\n",
			cssdata
		])

	def serve_frame(self, status, protocol, request):
		status = '200 Have A Look'
		host = "%s:%s" % request.hostinfo
		uri = '?'.join(request.url()[1].split('?')[1:])
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

		self._DirectResponse__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/html\r\n'\
				'\r\n%s' % ( status, '\n'.join( lines ) )

	def serve_params(self, status, protocol, request):
		msg = Command.print_info(True)
		self.prepare_buffer(status, json_write(msg), mime='application/json')

	def serve_descriptor(self, status, protocol, request):
		"""
			/page-info?<netpath>
		"""
		assert isinstance( request.url, basestring )
		q = urlparse.urlparse( request.url )[4]
		url = urlparse.urlparse(urllib.unquote(q))
		mainlog.warn([request.url, q, url])
		# Translate URL to cache location
		if ':' in url[1]:
			hostinfo = url[1].split(':')
			hostinfo[1] = int(hostinfo[1])
		else:
			hostinfo = url[1], 80
		if hostinfo[1] and hostinfo[1] == 80:
			port = ''
		else:
			port = ':'+str(port)
		netpath = "//%s%s%s" % ( hostinfo[0], port, url[2])
		# Get resource for (translated) netpath
		data = Resource.ProxyData(protocol)
		data.init_data(netpath)
		if data:
			self.prepare_buffer(status,
					json_write(data.descriptor.copyDict()),
					mime='application/json')
		else:
			self.prepare_buffer("404 No Data",
					"No data for %s"%netpath)

	def serve_script(self, status, protocol, request):
		jsdata = open(Params.PROXY_INJECT_JS).read()
		self._DirectResponse__sendbuf = "\r\n".join( [
			"HTTP/1.1 %s" % status,
			"Content-Type: application/javascript\r\n"
			"Access-Control-Allow-Origin: *\r\n",
			jsdata
		])

	def finalize(self, client):
		if self.action == 'reload_proxy':
			client.close()
			raise fiber.Restart()

	def __str__(self):
		return "[ProxyResponse %s]" % hex(id(self))


class NotFoundResponse( DirectResponse ):

	def __init__( self, protocol, request ):

		DirectResponse.__init__( self, '404 Not Found', request )


class ExceptionResponse( DirectResponse ):

	def __init__( self, request ):

		traceback.print_exc()
		DirectResponse.__init__( self, '500 Internal Server Error', request )
