"""
"""
import calendar, os, re, socket, sys, time

import Params, Runtime, Response, Cache
import log



mainlog = log.get_log('main')



DNSCache = {}

def connect( addr):

	assert Runtime.ONLINE, \
			'operating in off-line mode'
	if addr not in DNSCache:
		mainlog.debug('Requesting address info for %s:%i', *addr)
		DNSCache[ addr ] = socket.getaddrinfo( addr[ 0 ], addr[ 1 ], Runtime.FAMILY, socket.SOCK_STREAM )

	family, socktype, proto, canonname, sockaddr = DNSCache[ addr ][ 0 ]

	mainlog.info('Connecting to %s:%i', *sockaddr)
	sock = socket.socket( family, socktype, proto )
	sock.setblocking( 0 )
	sock.connect_ex( sockaddr )

	return sock


class BlindProtocol:

	Response = None

	def __init__(self, request):

		self.__socket = connect( request.url()[ :2 ] )
		self.__sendbuf = request.recvbuf()

	def socket(self):

		return self.__socket

	def recvbuf(self):

		return ''

	def hasdata(self):

		return True

	def send(self, sock):

		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]
		if not self.__sendbuf:
			self.Response = Response.BlindResponse

	def done(self):

		pass


SCRAP = []
def init_scrap():
	if os.path.isfile(Runtime.SCRAP):
		[re.compile(p.strip()) for p in open(Runtime.SCRAP).readlines()]

class HttpProtocol(Cache.File):

	Response = None

	def __init__(self, request):
		host, port, path = request.url()	
		for pattern in SCRAP:
			if pattern.match("%s/%s" % (host, path)):
				self.Response = Response.DirectResponse
				mainlog.note('Dropping connection.')

		Cache.File.__init__(self, '%s:%i/%s' % request.url() )

		if Runtime.STATIC and self.full():
			mainlog.note('Static mode; serving file directly from cache')
			self.__socket = None
			self.open_full()
			self.Response = Response.DataResponse
			return

		head = 'GET /%s HTTP/1.1' % request.url()[ 2 ]
		args = request.headers()
		args.pop( 'Accept-Encoding', None )
		args.pop( 'Range', None )
		stat = self.partial() or self.full()
		if stat:
			size = stat.st_size
			mtime = time.strftime( Params.TIMEFMT, time.gmtime( stat.st_mtime ) )
			if self.partial():
				if Runtime.VERBOSE: 
					mainlog.debug('Requesting resume of partial file in cache: %i bytes, %s' % ( size, mtime ))
				args[ 'Range' ] = 'bytes=%i-' % size
				args[ 'If-Range' ] = mtime
			else:
				if Runtime.VERBOSE: 
					mainlog.debug('Checking complete file in cache: %i bytes, %s' % ( size, mtime ))
				args[ 'If-Modified-Since' ] = mtime

		self.__socket = connect( request.url()[ :2 ] )
		self.__sendbuf = '\r\n'.join( [ head ] + map( ': '.join, args.items() ) + [ '', '' ] )
		self.__recvbuf = ''
		self.__parse = HttpProtocol.__parse_head

	def hasdata(self):
		"Indicator wether Protocol object has more request data available. "
		return bool( self.__sendbuf )

	def send(self, sock):
		"fiber hook to send request data. "
		assert self.hasdata()

		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]

	def __parse_head(self, chunk):

		eol = chunk.find( '\n' ) + 1
		if eol == 0:
			return 0

		line = chunk[ :eol ]
		mainlog.note("%s: Server responds %r", self, line.strip())
		fields = line.split()
		assert (2 <= len( fields )) \
			and fields[ 0 ].startswith( 'HTTP/' ) \
			and fields[ 1 ].isdigit(), 'invalid header line: %r' % line
		self.__status = int( fields[ 1 ] )
		self.__message = ' '.join( fields[ 2: ] )
		self.__args = {}
		mainlog.info("%s: finished parse_head (%s, %s)", self, self.__status, self.__message)
		self.__parse = HttpProtocol.__parse_args
		return eol

	def __parse_args(self, chunk):

		eol = chunk.find( '\n' ) + 1
		if eol == 0:
			return 0

		line = chunk[ :eol ]
		if ':' in line:
			mainlog.debug('> '+ line.rstrip())
			key, value = line.split( ':', 1 )
			# XXX: title caps improper for acronyms
			key = key.title()
			if key in self.__args:
				self.__args[ key ] += '\r\n' + key + ': ' + value.strip()
			else:
				self.__args[ key ] = value.strip()
		elif line in ( '\r\n', '\n'):
			self.__parse = None
		else:
			mainlog.err('Error: ignored server response header line: '+ line)

		return eol

	def recv(self, sock):

		assert not self.hasdata()

		chunk = sock.recv( Runtime.MAXCHUNK, socket.MSG_PEEK )
		mainlog.debug("%s: recv'd chunk (%i)", self, len(chunk))
		assert chunk, 'server closed connection before sending a complete message header'
		self.__recvbuf += chunk
		while self.__parse:
			bytecnt = self.__parse(self, self.__recvbuf )
			#assert bytecnt
			if not bytecnt:
				sock.recv( len( chunk ) )
				return
			self.__recvbuf = self.__recvbuf[ bytecnt: ]
		sock.recv( len( chunk ) - len( self.__recvbuf ) )

		if self.__status == 200:

			self.open_new()
			if 'Last-Modified' in self.__args:
				try:	
					self.mtime = calendar.timegm( time.strptime( self.__args[
						'Last-Modified' ], Params.TIMEFMT ) )
				except:
					print 'Illegal time format in Last-Modified: %s.' % self.__args[ 'Last-Modified' ]
					tmhdr = re.sub('\ [GMT0\+-]+$', '', self.__args[ 'Last-Modified' ])
					self.mtime = calendar.timegm( time.strptime( tmhdr, Params.TIMEFMT[:-4] ) )
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

			# TODO: self.__args['Content-Type'] = ct
			self.open_full()
			self.Response = Response.DataResponse

		elif self.__status in ( 403, 416 ) and self.partial():

			self.remove_partial()
			self.Response = Response.BlindResponse

		else:

			self.Response = Response.BlindResponse

		#if self.__status in (200, 206):
		#	ct=self.__args.get('Content-Type', None)
		#	if ct:
		#		open(self._File__path +'.mediatype', 'w').write(ct)

	def recvbuf(self):

		return '\r\n'.join( [ 'HTTP/1.1 %i %s' % ( self.__status, self.__message ) ] + map( ': '.join, self.__args.items() ) + [ '', '' ] )

	def headers(self):
		return self.__args.copy()

	def socket(self):
		return self.__socket


class FtpProtocol( Cache.File):

	Response = None

	def __init__(self, request):

		Cache.File.__init__(self, '%s:%i/%s' % request.url() )

		if Runtime.STATIC and self.full():
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

	def socket(self):
		return self.__socket

	def hasdata(self):
		return self.__sendbuf != ''

	def send(self, sock):
		assert self.hasdata()

		bytecnt = sock.send( self.__sendbuf )
		self.__sendbuf = self.__sendbuf[ bytecnt: ]

	def recv(self, sock):
		assert not self.hasdata()

		chunk = sock.recv( Runtime.MAXCHUNK )
		assert chunk, 'server closed connection prematurely'
		self.__recvbuf += chunk
		while '\n' in self.__recvbuf:
			reply, self.__recvbuf = self.__recvbuf.split( '\n', 1 )
			mainlog.debug('S: %s', reply.rstrip())
			if reply[ :3 ].isdigit() and reply[ 3 ] != '-':
				self.__handle(self, int( reply[ :3 ] ), reply[ 4: ] )
				mainlog.debug('C: %s', self.__sendbuf.rstrip())

	def __handle_serviceready(self, code, line):
		assert code == 220, \
				'server sends %i; expected 220 (service ready)' % code
		self.__sendbuf = 'USER anonymous\r\n'
		self.__handle = FtpProtocol.__handle_password

	def __handle_password(self, code, line):
		assert code == 331, \
				'server sends %i; expected 331 (need password)' % code
		self.__sendbuf = 'PASS anonymous@\r\n'
		self.__handle = FtpProtocol.__handle_loggedin

	def __handle_loggedin(self, code, line):
		assert code == 230, \
				'server sends %i; expected 230 (user logged in)' % code
		self.__sendbuf = 'TYPE I\r\n'
		self.__handle = FtpProtocol.__handle_binarymode

	def __handle_binarymode(self, code, line):
		assert code == 200, \
				'server sends %i; expected 200 (binary mode ok)' % code
		self.__sendbuf = 'PASV\r\n'
		self.__handle = FtpProtocol.__handle_passivemode

	def __handle_passivemode(self, code, line):
		assert code == 227, \
				'server sends %i; expected 227 (passive mode)' % code
		channel = eval( line.split()[ -1 ].strip('.') )
		addr = '%i.%i.%i.%i' % channel[ :4 ], channel[ 4 ] * 256 + channel[ 5 ]
		self.__socket = connect( addr )
		self.__sendbuf = 'SIZE %s\r\n' % self.__path
		self.__handle = FtpProtocol.__handle_size

	def __handle_size(self, code, line):
		if code == 550:
			self.Response = Response.NotFoundResponse
			return
		assert code == 213, \
				'server sends %i; expected 213 (file status)' % code
		self.size = int( line )
		mainlog.debug('File size: %s' % self.size)
		self.__sendbuf = 'MDTM %s\r\n' % self.__path
		self.__handle = FtpProtocol.__handle_mtime

	def __handle_mtime(self, code, line):
		if code == 550:
			self.Response = Response.NotFoundResponse
			return
		assert code == 213, \
				'server sends %i; expected 213 (file status)' % code
		self.mtime = calendar.timegm( time.strptime( line.rstrip(), '%Y%m%d%H%M%S' ) )
		#if Runtime.VERBOSE:
		#	'Modification time:', time.strftime( Params.TIMEFMT, time.gmtime( self.mtime ) )
		mainlog.debug('Modification time: %s' % time.strftime(
			Params.TIMEFMT, time.gmtime( self.mtime ) ))
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

	def __handle_resume(self, code, line):
		assert code == 350, 'server sends %i; ' \
				'expected 350 (pending further information)' % code
		self.open_partial()
		self.__sendbuf = 'RETR %s\r\n' % self.__path
		self.__handle = FtpProtocol.__handle_data

	def __handle_data(self, code, line):
		if code == 550:
			self.Response = Response.NotFoundResponse
			return
		assert code == 150, \
				'server sends %i; expected 150 (file ok)' % code
		self.Response = Response.DataResponse

