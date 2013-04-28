"""
The Protocol object relays the client request, accumulates the server response
data, and combines it with the cached. From there the Response object
reads this to the client.
"""
import calendar, os, time, socket, re

import Params, Runtime, Response, Resource, Rules
from HTTP import HTTP
from util import *


class DNSLookupException(Exception):

    def __init__( self, addr, exc ):
        self.addr = addr
        self.exc = exc

    def __str__( self ):
        return "DNS lookup error for %s: %s" % ( self.addr, self.exc )


LOCALHOSTS = ( 'localhost', Runtime.HOSTNAME, '127.0.0.1', '127.0.1.1' )
DNSCache = {}

def connect( addr ):
    assert Runtime.ONLINE, \
            'operating in off-line mode'
    if addr not in DNSCache:
        log('Requesting address info for %s:%i' % addr, Params.LOG_DEBUG)
        try:
            DNSCache[ addr ] = socket.getaddrinfo(
                addr[ 0 ], addr[ 1 ], Runtime.FAMILY, socket.SOCK_STREAM )
        except Exception, e:
            raise DNSLookupException(addr, e)
    family, socktype, proto, canonname, sockaddr = DNSCache[ addr ][ 0 ]
    log('Connecting to %s:%i' % sockaddr, Params.LOG_INFO)
    sock = socket.socket( family, socktype, proto )
    sock.setblocking( 0 )
    sock.connect_ex( sockaddr )
    return sock


class BlindProtocol:

    """
    Blind protocol is used to aim for gracefull recovery upon unexpected
    requests.
    """

    Response = None

    def __init__( self, request ):
        self.__socket = connect( request.hostinfo )
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


class CachingProtocol(object):

    """
    Open cache and descriptor index for requested resources.

    Filter requests using Drop, NoCache and .. rules.
    """

    Response = None
    "the htcache response class"
    capture = None
    "XXX: old indicator to track hashsum of response entity."

    @property
    def url( self ):
        # XXX: update this with data from content-location
        return self.request.url

    def __init__( self, request):
        "Determine and open cache location, get descriptor backend. "
        super(CachingProtocol, self).__init__()

        self.request = request
        self.data = None

        # Track server response
        self.__status, self.__message = None, None

    def has_response( self ):
        return self.__status and self.__message

    def prepare_direct_response( self, request ):
        """
        Serve either a proxy page, a replacement for blocked content, of static
        content. All directly from local storage.

        Returns true on direct-response ready.
        """
        host, port = request.hostinfo
        verb, path, proto = request.envelope

        print self, 'prepare_direct_response'
        if port == Runtime.PORT:
            log("Direct request: %s" % path, Params.LOG_INFO)
            assert host in LOCALHOSTS, "Cannot service for %s" % host
            self.Response = Response.DirectResponse

        # XXX: Respond by writing message as plain text, e.g echo/debug it:
        #self.Response = Response.DirectResponse

        # Filter request by regex from rules.drop
        filtered_path = "%s%s" % ( host, path )
        m = Rules.Drop.match( filtered_path )
        if m:
            self.set_blocked_response( path )
            log('Dropping connection, '
                        'request matches pattern: %r.' % m, Params.LOG_NOTE)

    def prepare_nocache_response( self ):
        "Blindly respond for NoCache rule matches. "
        pattern = Rules.NoCache.match( self.url )
        if pattern:
            log('Not caching request, matches pattern: %r.' %
                pattern, Params.LOG_NOTE)
            self.Response = Response.BlindResponse
            return True

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

    def get_size( self ):
        return self.data.descriptor.size;
    def set_size( self, size ):
        self.data.descriptor.size = size
    size = property( get_size, set_size )

    def get_mtime( self ):
        return self.cache.mtime;
    def set_mtime( self, mtime ):
        self.cache.mtime = mtime
    mtime = property( get_mtime, set_mtime )

    def read( self, pos, size ):
        return self.cache.read( pos, size )

    def write( self, chunk ):
        return self.cache.write( chunk )

    def tell( self ):
        return self.cache.tell()

    def finish( self ):
        self.data.finish_response()

    def __str__(self):
        return "[CachingProtocol %s]" % hex(id(self))


class HttpProtocol(CachingProtocol):

    rewrite = None

    def __init__( self, request ):
        super(HttpProtocol, self).__init__(request)

        host, port = request.hostinfo
        verb, path, proto = request.envelope

        # Serve direct response 
        self.prepare_direct_response(request)
        if self.Response:
            self.__socket = None
            return

        # Prepare to forward request
        self.data = Resource.ProxyData( self )

        # Skip server-round trip in static mode
        if Runtime.STATIC and self.cache.full: # FIXME
            log('Static mode; serving file directly from cache', Params.LOG_NOTE)
            self.data.prepare_static()
            self.Response = Response.DataResponse
            return

        proxy_req_headers = self.data.prepare_request( request )

        log("Prepared request headers", Params.LOG_DEBUG)
        for key in proxy_req_headers:
            log('> %s: %s' % (
                key, proxy_req_headers[ key ].replace( '\r\n', ' > ' ) ),
                Params.LOG_DEBUG)

        # Forward request to remote server, fiber will handle this
        head = 'GET /%s HTTP/1.1' % path
        self.__socket = connect(request.hostinfo)
        self.__sendbuf = '\r\n'.join(
            [ head ] + map( ': '.join, proxy_req_headers.items() ) + [ '', '' ] )
        self.__recvbuf = ''
        # Proxy protocol continues in self.recv after server response haders are
        # parsed, before the response entity is read from the remote server
        self.__parse = HttpProtocol.__parse_head

    @property
    def cache( self ):
# XXX: the other way around?
        return self.data.cache

    def hasdata( self ):
        "Indicator wether Protocol object has more request data available. "
        return bool( self.__sendbuf )

    def send( self, sock ):
        "fiber hook to send request data. "
        assert self.hasdata(), "no data"

        bytecnt = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytecnt: ]

    def __parse_head( self, chunk ):
        eol = chunk.find( '\n' ) + 1
        if eol == 0:
            return 0
        line = chunk[ :eol ]
        get_log(Params.LOG_NOTE)("%s: Server responds %r", self, line.strip())
        fields = line.split()
        assert (2 <= len( fields )) \
            and fields[ 0 ].startswith( 'HTTP/' ) \
            and fields[ 1 ].isdigit(), 'invalid header line: %r' % line
        self.__status = int( fields[ 1 ] )
        self.__message = ' '.join( fields[ 2: ] )
        self.__args = {}
        get_log(Params.LOG_INFO)("%s: finished parse_head", self)
        self.__parse = HttpProtocol.__parse_args
        return eol

    def __parse_args( self, chunk ):
        eol = chunk.find( '\n' ) + 1
        if eol == 0:
            return 0
        line = chunk[ :eol ]
        if ':' in line:
            log('> '+ line.rstrip(), Params.LOG_DEBUG)
            key, value = line.split( ':', 1 )
            if key.lower() in HTTP.Header_Map:
                key = HTTP.Header_Map[key.lower()]
            else:
                log("Warning: %r not a known HTTP (response) header (%r)"% (
                        key,value.strip()), Params.LOG_WARN)
                key = key.title() # XXX: bad? :)
            if key in self.__args:
              self.__args[ key ] += '\r\n' + key + ': ' + value.strip()
            else:
              self.__args[ key ] = value.strip()
        elif line in ( '\r\n', '\n' ):
            get_log(Params.LOG_NOTE)("%s: finished parsing args", self)
            self.__parse = None
        else:
            log('Error: ignored server response header line: '+ line, Params.LOG_ERR)
        return eol

    def recv( self, sock ):

        """"
        Process server response until headers are fully parsed, then
        prepare response handler.
        """

        assert not self.hasdata(), "has data"

        chunk = sock.recv( Params.MAXCHUNK, socket.MSG_PEEK )
        get_log(Params.LOG_INFO)("%s: chunk (%i)", self, len(chunk))
        assert chunk, 'server closed connection before sending '\
                'a complete message header, '\
                'parser: %r, data: %r' % (self.__parse, self.__recvbuf)
        self.__recvbuf += chunk
        while self.__parse:
            bytecnt = self.__parse( self, self.__recvbuf )
            if not bytecnt:
                sock.recv( len( chunk ) )
                return
            self.__recvbuf = self.__recvbuf[ bytecnt: ]
        sock.recv( len( chunk ) - len( self.__recvbuf ) )

        # Header was parsed

# XXX: chunking..
#        assert self.__args.pop( 'Transfer-Encoding', None ) != 'chunked', \
#                "Chunked response: %s %s" % ( self.__status, self.url)

        # Check wether to step back now
        if self.prepare_nocache_response():
            self.data.descriptor = None
            return

        # Process and update headers before deferring to response class
        # 2xx
        if self.__status in ( HTTP.OK, ):

            get_log(Params.LOG_INFO)("%s: Caching new download. ", self)
            self.data.finish_request()
#            self.recv_entity()
            self.set_dataresponse();

        elif self.__status in ( HTTP.MULTIPLE_CHOICES, ):
            assert False, HTTP.MULTIPLE_CHOICES

        elif self.__status == HTTP.PARTIAL_CONTENT \
                and self.cache.partial:

            log("Updating partial download. ", Params.LOG_INFO)
            self.__args = self.data.prepare_response()
            if self.__args['ETag']:
                assert self.__args['ETag'].strip('"') == self.data.descriptor.etag, (
                        self.__args['ETag'], self.data.descriptor.etag )
            self.recv_part()
            self.set_dataresponse();

        # 3xx: redirects
        elif self.__status in (HTTP.FOUND,
                    HTTP.MOVED_PERMANENTLY,
                    HTTP.TEMPORARY_REDIRECT):

            self.data.finish_request()
# XXX:
            #location = self.__args.pop( 'Location', None )
#            self.descriptor.move( self.cache.path, self.__args )
#            self.cache.remove_partial()
            self.Response = Response.BlindResponse

        elif self.__status == HTTP.NOT_MODIFIED:

            assert self.cache.full, "XXX sanity"
            log("Reading complete file from cache at %s" %
                    self.cache.path, Params.LOG_INFO)
            self.data.finish_request()
            self.Response = Response.DataResponse

        # 4xx: client error
        elif self.__status in ( HTTP.FORBIDDEN, HTTP.METHOD_NOT_ALLOWED ):

            if self.data:
                self.data.set_broken( self.__status )
            self.Response = Response.BlindResponse

        elif self.__status in ( HTTP.NOT_FOUND, HTTP.GONE ):

            self.Response = Response.BlindResponse
            #if self.descriptor:
            #    self.descriptor.update( self.__args )

        elif self.__status in ( HTTP.REQUEST_RANGE_NOT_STATISFIABLE, ):
            if self.cache.partial:
                log("Warning: Cache corrupted?: %s" % self.url, Params.LOG_WARN)
                self.cache.remove_partial()
            elif self.cache.full:
                self.cache.remove_full()
# XXX
#            if self.descriptor:
#                self.descriptor.drop()
#                log("Dropped descriptor: %s" % self.url)
            self.Response = Response.BlindResponse

        else:
            log("Warning: unhandled: %s, %s" % (self.__status, self.url),
                    Params.LOG_WARN)
            self.Response = Response.BlindResponse

#    def recv_entity(self):
#        """
#        Prepare to receive new entity.
#        """
#        if self.cache.full:
#            log("HttpProtocol.recv_entity: overwriting cache: %s" %
#                    self.url, Params.LOG_NOTE)
#            self.cache.remove_full()
#            self.cache.open_new()
#        else:
#            log("HttpProtocol.recv_entity: new cache: %s" %
#                    self.url, Params.LOG_NOTE)
#            self.cache.open_new()
#            self.cache.stat()
#            assert self.cache.partial

    def recv_part(self):
        """
        Prepare to receive partial entity.
        """
        byterange = self.__args.pop( 'Content-Range', 'none specified' )
        assert byterange.startswith( 'bytes ' ), \
                'unhandled content-range type: %s' % byterange
        byterange, size = byterange[ 6: ].split( '/' )
        beg, end = byterange.split( '-' )
        self.size = int( size )
        # Sanity check
        assert self.size == int( end ) + 1, \
                "Complete range %r should match entity size of %s"%(end, self.size)
        self.cache.open_partial( int( beg ) )
        assert self.cache.partial, "Missing cache but receiving partial entity. "

    def set_dataresponse(self):
        mediatype = self.__args.get( 'Content-Type', None )
        if Runtime.PROXY_INJECT and mediatype and 'html' in mediatype:
            log("XXX: Rewriting HTML resource: "+self.url, Params.LOG_NOTE)
            self.rewrite = True
        te = self.__args.get( 'Transfer-Encoding', None ) 
        get_log(Params.LOG_INFO)("%s: set_dataresponse %s", self, te)
        if te == 'chunked':
            self.Response = Response.ChunkedDataResponse
        else:
            self.Response = Response.DataResponse

    def recvbuf( self ):
        return self.print_message()

    def print_message( self, args=None ):
        if not args:
            args = self.__args
        return '\r\n'.join(
            [ '%s %i %s' % (
                self.request.envelope[2],
                self.__status,
                self.__message ) ] +
            map( ': '.join, args.items() ) + [ '', '' ] )

    def responsebuf( self ):
        return self.print_message(self.__args)

    def args( self ):
        return self.__args.copy()

    def socket( self ):
        return self.__socket

    def __str__(self):
        return "[HttpProtocol %s]" % hex(id(self))


class FtpProtocol( CachingProtocol ):

    Response = None

    def __init__( self, request ):
        super(FtpProtocol, self).__init__( request )

        if Runtime.STATIC and self.cache.full:
          self.__socket = None
          log("Static FTP cache : %s" % self.url)
          self.cache.open_full()
          self.Response = Response.DataResponse
          return

        self.__socket = connect(request.hostinfo)
        self.__path = request.envelope[1]
        self.__sendbuf = ''
        self.__recvbuf = ''
        self.__handle = FtpProtocol.__handle_serviceready

    def socket( self ):
        return self.__socket

    def hasdata( self ):
        return self.__sendbuf != ''

    def send( self, sock ):
        assert self.hasdata()

        bytecnt = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytecnt: ]

    def recv( self, sock ):
        assert not self.hasdata()

        chunk = sock.recv( Params.MAXCHUNK )
        assert chunk, 'server closed connection prematurely'
        self.__recvbuf += chunk
        while '\n' in self.__recvbuf:
            reply, self.__recvbuf = self.__recvbuf.split( '\n', 1 )
            log('S: %s' % reply.rstrip(), 2)
            if reply[ :3 ].isdigit() and reply[ 3 ] != '-':
                self.__handle( self, int( reply[ :3 ] ), reply[ 4: ] )
                log('C: %s' % self.__sendbuf.rstrip(), 2)

    def __handle_serviceready( self, code, line ):
        assert code == 220, \
            'server sends %i; expected 220 (service ready)' % code
        self.__sendbuf = 'USER anonymous\r\n'
        self.__handle = FtpProtocol.__handle_password

    def __handle_password( self, code, line ):
        assert code == 331, \
            'server sends %i; expected 331 (need password)' % code
        self.__sendbuf = 'PASS anonymous@\r\n'
        self.__handle = FtpProtocol.__handle_loggedin

    def __handle_loggedin( self, code, line ):
        assert code == 230, \
            'server sends %i; expected 230 (user logged in)' % code
        self.__sendbuf = 'TYPE I\r\n'
        self.__handle = FtpProtocol.__handle_binarymode

    def __handle_binarymode( self, code, line ):
        assert code == 200,\
            'server sends %i; expected 200 (binary mode ok)' % code
        self.__sendbuf = 'PASV\r\n'
        self.__handle = FtpProtocol.__handle_passivemode

    def __handle_passivemode( self, code, line ):
        assert code == 227, \
            'server sends %i; expected 227 (passive mode)' % code
        channel = eval( line.strip('.').split()[ -1 ] )
        addr = '%i.%i.%i.%i' % channel[ :4 ], channel[ 4 ] * 256 + channel[ 5 ]
        self.__socket = connect( addr )
        self.__sendbuf = 'SIZE %s\r\n' % self.__path
        self.__handle = FtpProtocol.__handle_size

    def __handle_size( self, code, line ):
        if code == 550:
            self.Response = Response.NotFoundResponse
            return
        assert code == 213,\
            'server sends %i; expected 213 (file status)' % code
        self.size = int( line )
        log('File size: %s' % self.size)
        self.__sendbuf = 'MDTM %s\r\n' % self.__path
        self.__handle = FtpProtocol.__handle_mtime

    def __handle_mtime( self, code, line ):
        if code == 550:
            self.Response = Response.NotFoundResponse
            return
        assert code == 213, \
            'server sends %i; expected 213 (file status)' % code
        self.mtime = calendar.timegm( time.strptime(
            line.rstrip(), '%Y%m%d%H%M%S' ) )
        log('Modification time: %s' % time.strftime(
            Params.TIMEFMT, time.gmtime( self.mtime ) ))
        stat = self.cache.partial
        if stat and stat.st_mtime == self.mtime:
            self.__sendbuf = 'REST %i\r\n' % stat.st_size
            self.__handle = FtpProtocol.__handle_resume
        else:
            stat = self.cache.full
            if stat and stat.st_mtime == self.mtime:
                log("Unmodified FTP cache : %s" % self.url)
                self.cache.open_full()
                self.Response = Response.DataResponse
            else:
                self.cache.open_new()
                self.__sendbuf = 'RETR %s\r\n' % self.__path
                self.__handle = FtpProtocol.__handle_data

    def __handle_resume( self, code, line ):
        assert code == 350, 'server sends %i; ' \
            'expected 350 (pending further information)' % code
        self.cache.open_partial()
        self.__sendbuf = 'RETR %s\r\n' % self.__path
        self.__handle = FtpProtocol.__handle_data

    def __handle_data( self, code, line ):
        if code == 550:
            self.Response = Response.NotFoundResponse
            return
        assert code == 150, \
            'server sends %i; expected 150 (file ok)' % code
        self.Response = Response.DataResponse


class ProxyProtocol:

    """
    """

    Response = Response.DirectResponse

    def __init__( self, request ):
        method, reqname, proto = request.envelope
        assert reqname.startswith('/'), reqname
        self.reqname = reqname[1:]
        self.status = HTTP.OK
        if method is not 'GET':
            self.status = HTTP.METHOD_NOT_ALLOWED
        if self.reqname not in Response.DirectResponse.urlmap.keys():
            self.status = HTTP.NOT_FOUND
        assert proto in ('', 'HTTP/1.0', 'HTTP/1.1'), proto

    def socket( self ):
        return None

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

    def has_response(self):
        return False


