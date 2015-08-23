"""
Protocol takes over an client socket connection after an
incoming request has been parsed by Request.

Normally a protocol prepares the request to be forwarded,
and it opens a socket to the server so that fiber can continue.
Fiber then switches to uploading the request using data from the
protocol instances, and once done writes any response
back to the protocol instance.

Protocol adds each response bit to its receive buffer and
then parses as much as possible of the headers. Once the headers
are in, it will have set the Response type to use to download
everything back to the client.

TODO describe caching: how it writes contents to the file while writing the response to
client too.
"""

import calendar, os, time, socket, re

import Params, Response, Cache, Rules



class DNSLookupException(Exception):

	def __init__( self, addr, exc ):
		self.addr = addr
		self.exc = exc

	def __str__( self ):
		return "DNS lookup error for %s: %s" % ( self.addr, self.exc )


DNSCache = {}

def connect( addr ):

	assert Params.ONLINE, \
			'operating in off-line mode'
	if addr not in DNSCache:
		if Params.VERBOSE:
			print 'Requesting address info for %s:%i' % addr
		try:
			DNSCache[ addr ] = socket.getaddrinfo(
				addr[ 0 ], addr[ 1 ], Params.FAMILY, socket.SOCK_STREAM )
		except Exception, e:
			raise DNSLookupException(addr, e)
	family, socktype, proto, canonname, sockaddr = DNSCache[ addr ][ 0 ]

	if Params.VERBOSE:
		print 'Connecting to %s:%i' % sockaddr
	sock = socket.socket( family, socktype, proto )
	sock.setblocking( 0 )
	sock.connect_ex( sockaddr )

	return sock


class BlindProtocol:

	"""
	Blind protocol is used to attempt gracefull recovery upon unexpected requests.
	"""

	Response = None

	def __init__( self, request ):

		self.__socket = connect( request.url()[ :2 ] )
		self.__sendbuf = request.recvbuf()

	def socket( self ):

		return self.__socket

	def recvbuf( self ):

		return ''

	def hasdata( self ):

		return True

	def send( self, sock ):

		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]
		if not self.__sendbuf:
			self.Response = Response.BlindResponse

	def done( self ):

		pass


class CachingProtocol( Cache.File ):

	def prepare_direct_response( self, request ):
		"""
		Serve either a proxy page, a replacement for blocked content, of static
		self.content. All directly from local storage.

		Returns true on direct-response ready.
		"""
		host, port, path = request.url()

		# XXX: move this to request phase
		if port == Params.PORT:
			print "Direct request: %s", path
			localhosts = ( 'localhost', Params.HOSTNAME, '127.0.0.1', '127.0.1.1' )
			assert host in localhosts, "Cannot service for %s, use from %s" % (host, localhosts)
			self.Response = Response.ProxyResponse

		# Filter request by regex from rules.drop
		filtered_path = "%s/%s" % ( host, path )
		m = Rules.Drop.match( filtered_path )
		if m:
			self.set_blocked_response( path )
			print 'Dropping connection, '\
						'request matches pattern: %r.'% m

	def set_blocked_response( self, path ):
		"Respond to client by writing filter warning about blocked content. "
		if '?' in path or '#' in path:
			pf = path.find( '#' )
			pq = path.find( '?' )
			p = len( path )
			if pf > 0: p = pf
			if pq > 0: p = pq
			nameext = os.path.splitext( path[:p] )
		else:
			nameext = os.path.splitext( path )
		if len( nameext ) == 2 and nameext[1][1:] in Params.IMG_TYPE_EXT:
			self.Response = Response.BlockedImageContentResponse
		else:
			self.Response = Response.BlockedContentResponse



class HttpProtocol( CachingProtocol ):

	Response = None
	"The type of response for fiber to use next"

	def __init__( self, request ):

		"""
		Initializes to forward client request.
		Updates request and sets send-buffer, and opens socket to the server
		so the fiber can upload the request, and then write any response back here.
		See HttpProtocol.{send,recv}.

		The receive routine parses the data, and once self.Response is set, the
		other functions will return details about the server-response.

		However, this init routine may intercept and skip all that, setting
		self.Repsonse immediatly in response to a filtered, static or direct request.
		"""

		Cache.File.__init__( self, '%s:%i/%s' % request.url() )

		# Serve direct response
		self.prepare_direct_response(request)
		if self.Response:
			self.__socket = None
			return

		if Params.STATIC and self.full():
			print 'Static mode; serving file directly from cache'
			self.__socket = None
			self.open_full()
			self.Response = Response.DataResponse
			return

		head = 'GET /%s HTTP/1.1' % request.url()[ 2 ]
		args = request.args()
		args.pop( 'Accept-Encoding', None )
		args.pop( 'Range', None )
		stat = self.partial() or self.full()
		if stat:
			size = stat.st_size
			mtime = time.strftime( Params.TIMEFMT, time.gmtime( stat.st_mtime ) )
			if self.partial():
				print 'Requesting resume of partial file in cache: %i bytes, %s' % ( size, mtime )
				args[ 'Range' ] = 'bytes=%i-' % size
				args[ 'If-Range' ] = mtime
			else:
				print 'Checking complete file in cache: %i bytes, %s' % ( size, mtime )
				args[ 'If-Modified-Since' ] = mtime

		self.__socket = connect( request.url()[ :2 ] )
		self.__sendbuf = '\r\n'.join( [ head ] + map( ': '.join, args.items() ) + [ '', '' ] )
		self.__recvbuf = ''
		self.__parse = HttpProtocol.__parse_head

	def hasdata( self ):

		return bool( self.__sendbuf )

	def send( self, sock ):

		assert self.hasdata()

		bytes = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytes: ]

	def __parse_head( self, chunk ):

		eol = chunk.find( '\n' ) + 1
		if eol == 0:
			return 0

		line = chunk[ :eol ]
		print 'Server responds', line.rstrip()
		fields = line.split()
		assert len( fields ) >= 3 and fields[ 0 ].startswith( 'HTTP/' ) and fields[ 1 ].isdigit(), 'invalid header line: %r' % line
		self.__status = int( fields[ 1 ] )
		self.__message = ' '.join( fields[ 2: ] )
		self.__args = {}
		self.__parse = HttpProtocol.__parse_args

		return eol

	def __parse_args( self, chunk ):

		eol = chunk.find( '\n' ) + 1
		if eol == 0:
			return 0

		line = chunk[ :eol ]
		if ':' in line:
			if Params.VERBOSE > 1:
				print '>', line.rstrip()
			key, value = line.split( ':', 1 )
			key = key.title()
			if key in self.__args:
				self.__args[ key ] += '\r\n' + key + ': ' + value.strip()
			else:
				self.__args[ key ] = value.strip()
		elif line in ( '\r\n', '\n' ):
			self.__parse = None
		else:
			print 'Ignored header line:', line

		return eol

	def recv( self, sock ):

		assert not self.hasdata()

		chunk = sock.recv( Params.MAXCHUNK, socket.MSG_PEEK )
		assert chunk, 'server closed connection before sending a complete message header'
		self.__recvbuf += chunk
		while self.__parse:
			bytecnt = self.__parse( self, self.__recvbuf )
			if not bytecnt:
				sock.recv( len( chunk ) )
				return
			self.__recvbuf = self.__recvbuf[ bytecnt: ]
		sock.recv( len( chunk ) - len( self.__recvbuf ) )

		# Process and update headers before deferring to response class
		# 2xx
		if self.__status == 200:

			self.open_new()
			if 'Last-Modified' in self.__args:
				self.mtime = calendar.timegm( time.strptime( self.__args[ 'Last-Modified' ], Params.TIMEFMT ) )
			if 'Content-Length' in self.__args:
				self.size = int( self.__args[ 'Content-Length' ] )
			if self.__args.pop( 'Transfer-Encoding', None ) == 'chunked':
				self.Response = Response.ChunkedDataResponse
			else:
				self.Response = Response.DataResponse

		elif self.__status == 206 and self.partial():

			range = self.__args.pop( 'Content-Range', 'none specified' )
			assert range.startswith( 'bytes ' ), 'invalid content-range: %s' % range
			range, size = range[ 6: ].split( '/' )
			beg, end = range.split( '-' )
			self.size = int( size )
			assert self.size == int( end ) + 1
			self.open_partial( int( beg ) )
			if self.__args.pop( 'Transfer-Encoding', None ) == 'chunked':
				self.Response = Response.ChunkedDataResponse
			else:
				self.Response = Response.DataResponse

		elif self.__status == 304 and self.full():

			self.open_full()
			self.Response = Response.DataResponse

		elif self.__status in ( 403, 416 ) and self.partial():

			self.remove_partial()
			self.Response = Response.BlindResponse

		else:

			self.Response = Response.BlindResponse

	def recvbuf( self ):
		return self.print_message()

	def print_message( self, args=None ):
		if not args:
			args = self.__args
		return '\r\n'.join(
			[ 'HTTP/1.1 %i %s' % (
				self.__status,
				self.__message ) ] +
			map( ': '.join, self.__args.items() ) + [ '', '' ] )

	def args( self ):

		try:
			return self.__args.copy()
		except AttributeError, e:
			return {}

	def socket( self ):

		return self.__socket

	def __str__(self):
		return "[HttpProtocol %s]" % hex(id(self))


class FtpProtocol( CachingProtocol ):

	Response = None

	def __init__( self, request ):

		Cache.File.__init__( self, '%s:%i/%s' % request.url() )

		if Params.STATIC and self.full():
			self.__socket = None
			self.open_full()
			self.Response = Response.DataResponse
			return

		host, port, path = request.url()
		self.__socket = connect(( host, port ))
		self.__path = path
		self.__sendbuf = ''
		self.__recvbuf = ''
		self.__handle = FtpProtocol.__handle_serviceready

	def socket( self ):

		return self.__socket

	def hasdata( self ):

		return self.__sendbuf != ''

	def send( self, sock ):

		assert self.hasdata()

		bytes = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytes: ]

	def recv( self, sock ):

		assert not self.hasdata()

		chunk = sock.recv( Params.MAXCHUNK )
		assert chunk, 'server closed connection prematurely'
		self.__recvbuf += chunk
		while '\n' in self.__recvbuf:
			reply, self.__recvbuf = self.__recvbuf.split( '\n', 1 )
			if Params.VERBOSE > 1:
				print 'S:', reply.rstrip()
			if reply[ :3 ].isdigit() and reply[ 3 ] != '-':
				self.__handle( self, int( reply[ :3 ] ), reply[ 4: ] )
				if self.__sendbuf and Params.VERBOSE > 1:
					print 'C:', self.__sendbuf.rstrip()

	def __handle_serviceready( self, code, line ):

		assert code == 220, 'server sends %i; expected 220 (service ready)' % code
		self.__sendbuf = 'USER anonymous\r\n'
		self.__handle = FtpProtocol.__handle_password

	def __handle_password( self, code, line ):

		assert code == 331, 'server sends %i; expected 331 (need password)' % code
		self.__sendbuf = 'PASS anonymous@\r\n'
		self.__handle = FtpProtocol.__handle_loggedin

	def __handle_loggedin( self, code, line ):

		assert code == 230, 'server sends %i; expected 230 (user logged in)' % code
		self.__sendbuf = 'TYPE I\r\n'
		self.__handle = FtpProtocol.__handle_binarymode

	def __handle_binarymode( self, code, line ):

		assert code == 200, 'server sends %i; expected 200 (binary mode ok)' % code
		self.__sendbuf = 'PASV\r\n'
		self.__handle = FtpProtocol.__handle_passivemode

	def __handle_passivemode( self, code, line ):

		assert code == 227, 'server sends %i; expected 227 (passive mode)' % code
		channel = eval( line.split()[ -1 ] )
		addr = '%i.%i.%i.%i' % channel[ :4 ], channel[ 4 ] * 256 + channel[ 5 ]
		self.__socket = connect( addr )
		self.__sendbuf = 'SIZE %s\r\n' % self.__path
		self.__handle = FtpProtocol.__handle_size

	def __handle_size( self, code, line ):

		if code == 550:
			self.Response = Response.NotFoundResponse
			return

		assert code == 213, 'server sends %i; expected 213 (file status)' % code
		self.size = int( line )
		print 'File size:', self.size
		self.__sendbuf = 'MDTM %s\r\n' % self.__path
		self.__handle = FtpProtocol.__handle_mtime

	def __handle_mtime( self, code, line ):

		if code == 550:
			self.Response = Response.NotFoundResponse
			return

		assert code == 213, 'server sends %i; expected 213 (file status)' % code
		self.mtime = calendar.timegm( time.strptime( line.rstrip(), '%Y%m%d%H%M%S' ) )
		print 'Modification time:', time.strftime( Params.TIMEFMT, time.gmtime( self.mtime ) )
		stat = self.partial()
		if stat and stat.st_mtime == self.mtime:
			self.__sendbuf = 'REST %i\r\n' % stat.st_size
			self.__handle = FtpProtocol.__handle_resume
		else:
			stat = self.full()
			if stat and stat.st_mtime == self.mtime:
				self.open_full()
				self.Response = Response.DataResponse
			else:
				self.open_new()
				self.__sendbuf = 'RETR %s\r\n' % self.__path
				self.__handle = FtpProtocol.__handle_data

	def __handle_resume( self, code, line ):

		assert code == 350, 'server sends %i; expected 350 (pending further information)' % code
		self.open_partial()
		self.__sendbuf = 'RETR %s\r\n' % self.__path
		self.__handle = FtpProtocol.__handle_data

	def __handle_data( self, code, line ):

		if code == 550:
			self.Response = Response.NotFoundResponse
			return

		assert code == 150, 'server sends %i; expected 150 (file ok)' % code
		self.Response = Response.DataResponse
