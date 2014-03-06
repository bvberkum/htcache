"""

TODO: determine cachability.


"""
import os, socket, time

import Params, Protocol
from HTTP import HTTP



class HtRequest:

	"""
	The single type for requests supported by htcache.
	This should cover HTTP and FTP.

	HtRequest.recv() wil finish once the entire request has been read,
	and choose the appropiate Protocol from HttpProtocol, FtpProtocol, or
	BlindProtocol.
	"""

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

		Params.log('Client sends %r'%Params.print_str(line, 96), threshold=1)
		fields = line.split()
		assert len( fields ) == 3, 'invalid header line: %r' % line
		self.__verb, self.__reqpath, self.__prototag = fields
		assert self.__reqpath, fields
		self.__headers = {}
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
			Params.log('> '+ line.rstrip(), 2)
			key, value = line.split( ':', 1 )
			if key.lower() in HTTP.Header_Map:
				key = HTTP.Header_Map[key.lower()]
			else:
				Params.log("Warning: %r not a known HTTP (request) header (%r)"%(
					key, value.strip()), 1)
				key = key.title() 
			assert key not in self.__headers, 'duplicate req. header: %s' % key
			self.__headers[ key ] = value.strip()
		elif line in ( '\r\n', '\n' ):
			self.__size = int( self.__headers.get( 'Content-Length', 0 ) )
			if self.__size:
				assert self.__verb == 'POST', \
						'%s request conflicts with message body' % self.__verb
				Params.log('Opening temporary file for POST upload', 1)
				self.__body = os.tmpfile()
				self.__parse = self.__parse_body
			else:
				self.__body = None
				self.__parse = None
		else:
			Params.log('Warning: Ignored header line: %r' % line)

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
		Receive request, parsing header and optional body. Once parsers have
		finished, determine wether 
		
		Resource, and prepare Protocol for relaying the request to the content
		origin server.
		"""

		assert not self.Protocol, "Cant have protocol"

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

		# Headers are parsed, determine target server and resource
		verb, proxied_url, proto = self.envelope

		scheme = ''
		host = ''
		port = Params.PORT
		path = ''

		# Accept http and ftp proxy requests
		if proxied_url.startswith( 'http://' ):
			if verb == 'GET':
				self.Protocol = Protocol.HttpProtocol
			else:
				self.Protocol = Protocol.BlindProtocol
			scheme = 'http'
			host = proxied_url[ 7: ]
			port = 80

		elif proxied_url.startswith( 'ftp://' ):
			assert verb == 'GET', \
					'%s request unsupported for ftp' % verb
			self.Protocol = Protocol.FtpProtocol
			scheme = 'ftp'
			host = proxied_url[ 6: ]
			port = 21

		elif proxied_url.startswith( '/' ):
			path = proxied_url
			host = socket.gethostname()
			self.Protocol = Protocol.ProxyProtocol

		else:
			# XXX self.Protocol = Protocol.BlindProtocol
			self.Protocol = Protocol.HttpProtocol
			scheme = ''
			host = '' 
			port = Params.PORT

		# Get the path
		if '/' in host:
			host, path = host.split( '/', 1 )
#		else:
#			path = ''

		# Parse hostinfo
		if ':' in host:
			hostinfo = host
			host, port = host.split( ':' )
			port = int( port )
		else:
			hostinfo = "%s:%s" % (host, port)

		Params.log('scheme=%s, host=%s, port=%s, path=%s' % 
				(scheme, host, port, path), 3)

		self.__scheme = scheme
		self.__host = host
		self.__port = port
		self.__reqpath = path

# FIXME: write a test for this
#		if self.resource and 'Host' not in self.__headers:
#			# Become HTTP/1.1 compliant
#			self.__headers['Host'] = self.resource.ref.host

		self.__headers[ 'Host' ] = host
		self.__headers[ 'Connection' ] = 'close'

		self.__headers.pop( 'Keep-Alive', None )
		self.__headers.pop( 'Proxy-Connection', None )
		self.__headers.pop( 'Proxy-Authorization', None )

		# Add Date (HTTP/1.1 [RFC 2616] 14.18)
		if 'Date' not in self.__headers:
			self.__headers[ 'Date' ] = time.strftime(
				Params.TIMEFMT, time.gmtime() )

		# Add proxy Via header (HTTP/1.1 [RFC 2616] 14.45)
		via = "1.1 %s:%i (htcache/%s)" % (Params.HOSTNAME, 
				Params.PORT,
				Params.VERSION)
		if self.__headers.setdefault('Via', via) != via:
			self.__headers['Via'] += ', '+ via

	def recvbuf( self ):
		assert self.Protocol, "No protocol yet"
		lines = [ '%s %s HTTP/1.1' % ( self.__verb, self.__reqpath ) ]
		lines.extend( map( ': '.join, self.__headers.items() ) )
		lines.append( '' )
		if self.__body:
			self.__body.seek( 0 )
			lines.append( self.__body.read() )
		else:
			lines.append( '' )
		return '\r\n'.join( lines )

	def is_conditional(self):
		return ( 'If-Modified-Since' in self.__headers
				or 'If-None-Match' in self.__headers )
		# XXX: If-Range

	@property
	def envelope(self):
		"""
		Used before protocol is determined. After recv finishes parsing
		Request.requrl and Request.hostinfo is used instead.
		"""
		return self.__verb.upper(), self.__reqpath, self.__prototag.upper()

	@property
	def hostinfo(self):
		return self.__host, self.__port

	@property
	def requri(self):
		assert self.Protocol, "Use request.envelope property. "
		return self.__scheme, self.__host, self.__port, self.__reqpath

	@property
	def url( self ):
		host, port = self.hostinfo

		# Prepare requri to identify request
		if port != 80:
			hostinfo = "%s:%s" % self.hostinfo
		else:
			hostinfo = host

		return "http://%s/%s" %  (hostinfo, self.__reqpath)

	@property
	def headers(self):
		# XXX: used before protocol is determined,  assert self.Protocol
		if not self.Protocol and self.__parse == self.__parse_args:
			Params.log("Warning: parsing headers is not finished. ")
		return self.__headers.copy()

	def range(self):
		byterange = self.__headers.get( 'Range' )
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
		assert self.Protocol, "no protocol"
		return hash(( self.__host, self.__port, self.__reqpath ))

	def __eq__( self, other ):
		assert self.Protocol, "no protocol"
		request1 = self.__verb,  self.__host,  self.__port,  self.__reqpath
		request2 = other.__verb, other.__host, other.__port, other.__reqpath
		return request1 == request2

	def __str__(self):
		return "<%s %s, %s>" % (Params.cn(self), self.hostinfo, self.envelope)

