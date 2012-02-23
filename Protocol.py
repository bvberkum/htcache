import calendar, os, time, socket, re

import Params, Response, Resource, Cache



LOCALHOSTS = ('localhost',socket.gethostname(),'127.0.0.1','127.0.1.1')
DNSCache = {}

def connect( addr ):
    assert Params.ONLINE, 'operating in off-line mode'
    if addr not in DNSCache:
        Params.log('Requesting address info for %s:%i' % addr)
        DNSCache[ addr ] = socket.getaddrinfo(
            addr[ 0 ], addr[ 1 ], Params.FAMILY, socket.SOCK_STREAM )
    family, socktype, proto, canonname, sockaddr = DNSCache[ addr ][ 0 ]
    Params.log('Connecting to %s:%i' % sockaddr)
    sock = socket.socket( family, socktype, proto )
    sock.setblocking( 0 )
    sock.connect_ex( sockaddr )
    return sock


class BlindProtocol:

    Response = None

    def __init__( self, request ):
        self.__socket = connect(request.hostinfo)
        self.__sendbuf = request.recvbuf()

    def socket( self ):
        return self.__socket

    def recvbuf( self ):
        return ''

    def hasdata( self ):
        return True

    def send( self, sock ):
        bytes = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytes: ]
        if not self.__sendbuf:
          self.Response = Response.BlindResponse

    def done( self ):
        pass



class ProxyProtocol(object):

    """
    Open cache and descriptor index for requested resources.
    Filter requests using DROP, NOCACHE and .. rules.
    """

    cache = None
    "resource entity storage"
    descriptors = None
    "resource descriptor storage"

    requri = None
    "requested resource ID, set by subclass"
    Response = None
    "the htcache response class"

    def __init__(self, request):
        "Determine and open cache location, get descriptor backend. "
        super(ProxyProtocol, self).__init__()
        url = request.hostinfo + (request.envelope[1],)
        cache_location = '%s:%i/%s' % url
        self.cache = Cache.load_backend_type(Params.CACHE)(cache_location)
        Params.log('Cache position: %s' % self.cache.path)
        self.descriptors = Resource.get_backend()

#    def has_descriptor(self):
#        return self.cache.path in self.descriptors and isinstance(self.get_descriptor(), tuple)
#
#    def get_descriptor(self):
#        return self.descriptors[self.cache.path]

    def prepare_direct_response(self, request):
        """
        Serve either a proxy page, a replacement for blocked content, of static
        content. All directly from local storage.

        Returns true on direct-response ready.
        """
        host, port = request.hostinfo
        verb, path, proto = request.envelope
        if port == 8080:
            Params.log("Direct request: %s" % path)
            assert host in LOCALHOSTS, "Cannot service for %s" % host
            self.Response = Response.DirectResponse
            return True
        # Respond by writing message as plain text, e.g echo/debug it:
        #self.Response = Response.DirectResponse
        # Filter request by regex from patterns.drop
        filtered_path = "%s/%s" % (host, path)
        for pattern, compiled in Params.DROP:
            if compiled.match(filtered_path):
                self.set_blocked_response(path)
                Params.log('Dropping connection, '
                            'request matches pattern: %r.' % pattern)
                return True
        if Params.STATIC and self.cache.full():
            Params.log('Static mode; serving file directly from cache')
            self.cache.open_full()
            self.Response = Response.DataResponse
            return True

    def prepare_filtered_response(self):
        "After parsing resheaders, return True "
        # XXX: matches on path only
        for pattern, compiled in Params.NOCACHE:
            #Params.log("nocache p %s" % pattern)
            if compiled.match(self.requri):
                self.Response = Response.BlindResponse
                Params.log('Not caching request, matches pattern: %r.' %
                    pattern)
                return True

    def set_blocked_response(self, path):
        "Respond to client by writing filter warning about blocked content. "
        if '?' in path or '#' in path:
            pf = path.find('#')
            pq = path.find('?')
            p = len(path)
            if pf > 0: p = pf
            if pq > 0: p = pq
            nameext = os.path.splitext(path[:p])
        else:
            nameext = os.path.splitext(path)
        if len(nameext) == 2 and nameext[1][1:] in Params.IMG_TYPE_EXT:
            self.Response = Response.BlockedImageContentResponse
        else:
            self.Response = Response.BlockedContentResponse

    def get_size(self):
        return self.cache.size;
    def set_size(self, size):
        self.cache.size = size
    size = property(get_size, set_size)

    def get_mtime(self):
        return self.cache.mtime;
    def set_mtime(self, mtime):
        self.cache.mtime = mtime
    mtime = property(get_mtime, set_mtime)

    def read(self, pos, size):
        return self.cache.read(pos, size)

    def write(self, chunk):
        return self.cache.write(chunk)

    def tell(self):
        return self.cache.tell()
#
#    def close(self):
#        return self.cache.close()
#
#    def __del__(self):
#        del self.cache


class HTTP:

    OK = 200
    PARTIAL_CONTENT = 206
    MULTIPLE_CHOICES = 300 # Variant resource, see alternatives list
    MOVED_TEMPORARILY = 301 # Located elsewhere
    FOUND = 302 # Moved permanently
    SEE_OTHER = 303 # Resource for request located elsewhere using GET
    NOT_MODIFIED = 304
    #USE_PROXY = 305
    _ = 306 # Reserved
    TEMPORARY_REDIRECT = 307 # Same as 302,
    # added to explicitly contrast with 302 mistreated as 303

    FORBIDDEN = 403
    GONE = 410
    REQUEST_RANGE_NOT_STATISFIABLE = 416

    Entity_Headers =  (
        # RFC 2616
        'Allow',
        'Content-Encoding',
        'Content-Language',
        'Content-Length',
        'Content-Location',
        'Content-MD5',
        'Content-Range',
        'Content-Type',
        'Expires',
        'Last-Modified',
    # extension-header
    )
    Request_Headers = (
        # RFC 2616
        'Accept',
        'Accept-Charset',
        'Accept-Encoding',
        'Accept-Language',
        'Authorization',
        'Expect',
        'From',
        'Host',
        'If-Match',
        'If-Modified-Since',
        'If-None-Match',
        'If-Range',
        'If-Unmodified-Since',
        'Max-Forwards',
        'Proxy-Authorization',
        'Range',
        'Referer',
        'TE',
        'User-Agent',
        # RFC 2295
        'Accept-Features',
        'Negotiate',
    )
    Response_Headers = (
        # RFC 2616
        'Accept-Ranges',
        'Age',
        'ETag',
        'Location',
        'Proxy-Authenticate',
        'Retry-After',
        'Server',
        'Vary',
        'WWW-Authenticate',
        # RFC 2295
        'Alternates',
        'TCN',
        'Variant-Vary',
    )
    Cache_Headers = Entity_Headers + (
        'ETag',
    )


    Message_Headers = Request_Headers + Response_Headers +\
            Entity_Headers + (
                    # Generic headers
                    # RFC 2616
                    'Date',
                    'Cache-Control', # RFC 2616 14.9
                    'Pragma', # RFC 2616 14.32
                )
    """
    For information on other registered HTTP headers, see RFC 4229.
    """


class HttpProtocol(ProxyProtocol):

    def __init__( self, request ):
        super(HttpProtocol, self).__init__(request)
    
        host, port = request.hostinfo
        verb, path, proto = request.envelope

        # Prepare requri to identify request
        if port != 80:
            hostinfo = "%s:%s" % (host, port)
        else:
            hostinfo = host
        self.requri = "http://%s/%s" %  (hostinfo, path)

        if self.prepare_direct_response(request):
            self.__socket = None
            return

        # Prepare request for contact with origin server..
        head = 'GET /%s HTTP/1.1' % path

        args = request.headers
        args.pop( 'Accept-Encoding', None )
        args.pop( 'Range', None )
        stat = self.cache.partial() or self.cache.full()
        if stat:
            size = stat.st_size
            mtime = time.strftime(
                Params.TIMEFMT, time.gmtime( stat.st_mtime ) )
            if self.cache.partial():
                Params.log('Requesting resume of partial file in cache: '
                    '%i bytes, %s' % ( size, mtime ), 1)
                args[ 'Range' ] = 'bytes=%i-' % size
                args[ 'If-Range' ] = mtime
            else:
                Params.log('Checking complete file in cache: %i bytes, %s' %
                    ( size, mtime ), 1)
                args[ 'If-Modified-Since' ] = mtime
        Params.log("Connecting to %s:%s" % request.hostinfo)
        self.__socket = connect(request.hostinfo)
        self.__sendbuf = '\r\n'.join(
            [ head ] + map( ': '.join, args.items() ) + [ '', '' ] )
        self.__recvbuf = ''
        self.__parse = HttpProtocol.__parse_head

    def hasdata( self ):
        return bool( self.__sendbuf )

    def send( self, sock ):
        assert self.hasdata(), "no data"

        bytes = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytes: ]

    def __parse_head( self, chunk ):
        eol = chunk.find( '\n' ) + 1
        if eol == 0:
            return 0

        line = chunk[ :eol ]
        Params.log('Server responds '+ line.rstrip())
        fields = line.split()
        assert (2 <= len( fields )) \
            and fields[ 0 ].startswith( 'HTTP/' ) \
            and fields[ 1 ].isdigit(), 'invalid header line: %r' % line
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
            Params.log('> '+ line.rstrip(), 1)
            key, value = line.split( ':', 1 )
            # TODO: store in headerdict
            if key in self.__args:
              self.__args[ key ] += '\r\n' + key + ': ' + value.strip()
            else:
              self.__args[ key ] = value.strip()
        elif line in ( '\r\n', '\n' ):
            self.__parse = None
        else:
            Params.log('Ignored header line: '+ line)

        return eol

    def recv( self, sock ):
        " Read until header can be parsed, then determine Response type. "
        assert not self.hasdata(), "has data"

        chunk = sock.recv( Params.MAXCHUNK, socket.MSG_PEEK )
        assert chunk, 'server closed connection before sending '\
                        'a complete message header'
        self.__recvbuf += chunk
        while self.__parse:
            bytes = self.__parse( self, self.__recvbuf )
            if not bytes:
                sock.recv( len( chunk ) )
                return
            self.__recvbuf = self.__recvbuf[ bytes: ]
        sock.recv( len( chunk ) - len( self.__recvbuf ) )

        if self.prepare_filtered_response():
            return

        if self.__status == HTTP.OK:
            self.cache.open_new()
            if 'Last-Modified' in self.__args:
                try:
                    self.mtime = calendar.timegm( time.strptime(
                        self.__args[ 'Last-Modified' ], Params.TIMEFMT ) )
                except:
                    Params.log('Illegal time format in Last-Modified: %s.' %
                        self.__args[ 'Last-Modified' ])
                    # Try again:
                    try:
                        tmhdr = re.sub('\ [GMT0\+-]+$', '',
                            self.__args[ 'Last-Modified' ])
                        self.mtime = calendar.timegm( time.strptime(
                            tmhdr, Params.TIMEFMT[:-4] ) )
                    except:
                        try:
                            self.mtime = calendar.timegm( time.strptime(
                                self.__args[ 'Last-Modified' ],
                                Params.ALTTIMEFMT ) )
                        except:
                            pass
            if 'Content-Length' in self.__args:
                self.size = int( self.__args[ 'Content-Length' ] )
            if self.__args.pop( 'Transfer-Encoding', None ) == 'chunked':
                self.Response = Response.ChunkedDataResponse
            else:
                self.Response = Response.DataResponse

        elif self.__status == HTTP.PARTIAL_CONTENT and self.cache.partial():
            byterange = self.__args.pop( 'Content-Range', 'none specified' )
            assert byterange.startswith( 'bytes ' ), \
                'unhandled content-range type: %s' % byterange
            byterange, size = byterange[ 6: ].split( '/' )
            beg, end = byterange.split( '-' )
            self.size = int( size )
            assert self.size == int( end ) + 1, (self.size, end)
            self.cache.open_partial( int( beg ) )
            if self.__args.pop( 'Transfer-Encoding', None ) == 'chunked':
              self.Response = Response.ChunkedDataResponse
            else:
              self.Response = Response.DataResponse

        elif self.__status == HTTP.NOT_MODIFIED and self.cache.full():
            # FIXME: update last-modified?
            self.cache.open_full()
            self.Response = Response.DataResponse

        elif self.__status in ( HTTP.FORBIDDEN, \
                    HTTP.REQUEST_RANGE_NOT_STATISFIABLE ) \
                    and self.cache.partial():
            self.cache.remove_partial()
            self.Response = Response.BlindResponse

        elif self.__status in (HTTP.FOUND, HTTP.MOVED_TEMPORARILY,
                    HTTP.TEMPORARY_REDIRECT):
            location = self.__args['Location']
            self.Response = Response.BlindResponse

        else:
            self.Response = Response.BlindResponse

        # Update descriptor
        if self.__status in (HTTP.OK, HTTP.PARTIAL_CONTENT):
            pass # TODO: srcrefs, mediatype, charset, language, 
            self.descriptors[self.cache.path] = [self.requri], self.__args

    def recvbuf( self ):
        return '\r\n'.join(
            [ 'HTTP/1.1 %i %s' % ( self.__status, self.__message ) ] +
            map( ': '.join, self.__args.items() ) + [ '', '' ] )

    def args( self ):
        return self.__args.copy()

    def socket( self ):
        return self.__socket


class FtpProtocol( ProxyProtocol ):

    Response = None

    def __init__( self, request ):
        super(FtpProtocol, self).__init__( request )

        if Params.STATIC and self.cache.full():
          self.__socket = None
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

        bytes = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytes: ]

    def recv( self, sock ):
        assert not self.hasdata()

        chunk = sock.recv( Params.MAXCHUNK )
        assert chunk, 'server closed connection prematurely'
        self.__recvbuf += chunk
        while '\n' in self.__recvbuf:
            reply, self.__recvbuf = self.__recvbuf.split( '\n', 1 )
            Params.log('S: %s' % reply.rstrip(), 2)
            if reply[ :3 ].isdigit() and reply[ 3 ] != '-':
                self.__handle( self, int( reply[ :3 ] ), reply[ 4: ] )
                Params.log('C: %s' % self.__sendbuf.rstrip(), 2)

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
        channel = eval( line.split()[ -1 ] )
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
        Params.log('File size: %s' % self.size)
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
        Params.log('Modification time: %s' % time.strftime(
            Params.TIMEFMT, time.gmtime( self.mtime ) ))
        stat = self.cache.partial()
        if stat and stat.st_mtime == self.mtime:
            self.__sendbuf = 'REST %i\r\n' % stat.st_size
            self.__handle = FtpProtocol.__handle_resume
        else:
            stat = self.cache.full()
            if stat and stat.st_mtime == self.mtime:
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


