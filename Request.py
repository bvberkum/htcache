import Params, Protocol, socket, os


class HttpRequest:

	Protocol = None

	def __init__( self ):

		self.__parse = self.__parse_head
		self.__recvbuflen = 0
		self.__recvbuf = ''

	def __parse_head( self, chunk ):

		"""
		Start parsing request by splitting the envelope or request line,
		defer to __parse_args once first line has been received.
		"""

		eol = chunk.find( '\n' ) + 1
		if eol == 0:
			return 0

		line = chunk[ :eol ]
		print 'Client sends', line.rstrip()
		fields = line.split()
		assert len( fields ) == 3, 'Invalid header line: %r' % line

		self.__verb, self.__url, dummy = fields
		self.__args = {}
		self.__parse = self.__parse_args

		return eol

	def __parse_args( self, chunk ):

		"""
		Parse request header. Defer to __parse_body if request entity body
		is indicated.
		"""

		eol = chunk.find( '\n' ) + 1
		if eol == 0:
			return 0

		line = chunk[ :eol ]
		if ':' in line:
			if Params.VERBOSE > 1:
				print '>', line.rstrip()
			key, value = line.split( ':', 1 )
			key = key.title()
			assert key not in self.__args, 'duplicate key: %s' % key
			self.__args[ key ] = value.strip()
		elif line in ( '\r\n', '\n' ):
			self.__size = int( self.__args.get( 'Content-Length', 0 ) )
			if self.__size:
				assert self.__verb == 'POST', '%s request conflicts with message body' % self.__verb
				if Params.VERBOSE:
					print 'Opening temporary file for POST upload'
				self.__body = os.tmpfile()
				self.__parse = self.__parse_body
			else:
				self.__body = None
				self.__parse = None
		else:
			print 'Ignored header line: %r' % line

		return eol

	def __parse_body( self, chunk ):
		"""
		Parse request body.
		"""

		self.__body.write( chunk )
		assert self.__body.tell() <= self.__size, \
				'message body exceeds content-length'
		if self.__body.tell() == self.__size:
			self.__parse = None

		return len( chunk )

	def recv( self, sock ):

		"""
		Receive request from client, parsing header and optional body. 
		Once parsers have finished, determine Protocol type for htcache/fiber.

		The Protocol instance takes over and relays this request to the 
		target server.
		"""

		assert not self.Protocol

		chunk = sock.recv( Params.MAXCHUNK )
		assert chunk, \
				'client closed connection before sending a '\
				'complete message header at %s, ' \
				'parser: %r, data: %r' % (
						self.__recvbuflen, self.__parse, self.__recvbuf)
		self.__recvbuf += chunk
		self.__recvbuflen += len(chunk)
		while self.__parse:
			bytecnt = self.__parse( self.__recvbuf )
			if not bytecnt:
				return
			self.__recvbuf = self.__recvbuf[ bytecnt: ]
		assert not self.__recvbuf, 'client sends junk data after message header'

		if self.__url.startswith( 'http://' ):
			host = self.__url[ 7: ]
			port = 80
			if self.__verb == 'GET':
				self.Protocol = Protocol.HttpProtocol
			else:
				self.Protocol = Protocol.BlindProtocol
		elif self.__url.startswith( 'ftp://' ):
			assert self.__verb == 'GET', '%s request unsupported for ftp' % self.__verb
			self.Protocol = Protocol.FtpProtocol
			host = self.__url[ 6: ]
			port = 21
		else:
			raise AssertionError, 'invalid url: %s' % self.__url
		if '/' in host:
			host, path = host.split( '/', 1 )
			path = '/'+path
		else:
			path = '/'
		if ':' in host:
			host, port = host.split( ':' )
			port = int( port )

		self.__host = host
		self.__port = port
		self.__path = path
		self.__args[ 'Host' ] = host
		self.__args[ 'Connection' ] = 'close'
		self.__args.pop( 'Keep-Alive', None )
		self.__args.pop( 'Proxy-Connection', None )
		self.__args.pop( 'Proxy-Authorization', None )

		# add	proxy via header
		via = "%s:%i" % (socket.gethostname(), Params.PORT)
		if self.__args.setdefault('Via', via) != via:
			self.__args['Via'] += ', '+ via

	def recvbuf( self ):

		assert self.Protocol
		lines = [ '%s /%s HTTP/1.1' % ( self.__verb, self.__path ) ]
		lines.extend( map( ': '.join, self.__args.items() ) )
		lines.append( '' )
		if self.__body:
			self.__body.seek( 0 )
			lines.append( self.__body.read() )
		else:
			lines.append( '' )

		return '\r\n'.join( lines )

	def url( self ):

		assert self.Protocol
		return self.__host, self.__port, self.__path

	def headers( self ):

		assert self.Protocol
		return self.__args.copy()

	def range( self ):

		byterange = self.__args.get( 'Range' )
		if not byterange:
			return 0, -1
		try:
			assert byterange.startswith( 'bytes=' )
			beg, end = byterange[ 6: ].split( '-' )
			if not beg:
				return int( end ), -1
			elif not end:
				return int( beg ), -1
			else:
				return int( beg ), int( end ) + 1
		except:
			raise AssertionError, \
				'invalid byterange specification: %s' % byterange

	def __hash__( self ):

		assert self.Protocol
		assert self.__path[0] == '/', self.__path
		return hash( self.__path )

	def __eq__( self, other ):

		assert self.Protocol
		request1 = self.__verb,	self.__host,	self.__port,	self.__path
		request2 = other.__verb, other.__host, other.__port, other.__path
		return request1 == request2

