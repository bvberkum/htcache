"""
The Protocol object relays the client request, accumulates the server response
data, and combines it with the cached. From there the Response object
reads this to the client.
"""
import calendar, os, time, socket, re

import Params, Response, Resource, Cache, Rules
from HTTP import HTTP


class DNSLookupException(Exception):

    def __init__( self, addr, exc ):
        self.addr = addr
        self.exc = exc

    def __str__( self ):
        return "DNS lookup error for %s: %s" % ( self.addr, self.exc )


LOCALHOSTS = ( 'localhost', Params.HOSTNAME, '127.0.0.1', '127.0.1.1' )
DNSCache = {}

def connect( addr ):
    assert Params.ONLINE, \
            'operating in off-line mode'
    if addr not in DNSCache:
        Params.log('Requesting address info for %s:%i' % addr, 2)
        try:
            DNSCache[ addr ] = socket.getaddrinfo(
                addr[ 0 ], addr[ 1 ], Params.FAMILY, socket.SOCK_STREAM )
        except Exception, e:
            raise DNSLookupException(addr, e)
    family, socktype, proto, canonname, sockaddr = DNSCache[ addr ][ 0 ]
    Params.log('Connecting to %s:%i' % sockaddr, 3)
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


class ProxyProtocol(object):

    """
    Open cache and descriptor index for requested resources.

    Filter requests using DROP, NOCACHE and .. rules.
    """

    cache = None
    "resource entity storage"
    descriptors = None
    "resource descriptor storage"

    Response = None
    "the htcache response class"
    capture = None
    "XXX: old indicator to track hashsum of response entity."

    def __init__( self, request, prepcache=True ):
        "Determine and open cache location, get descriptor backend. "
        super( ProxyProtocol, self ).__init__()

        self.request = request

        # Track server response
        self.__status, self.__message = None, None

        if prepcache:
            self.init_cache()

    def init_cache(self):
        p = self.url.find( ':' ) # find len of scheme-id
        assert self.url[p:p+3] == '://', self.url
        self.cache = Cache.load_backend_type(Params.CACHE)(self.url[p+3:])
        Params.log("Init cache: %s %s" % (Params.CACHE, self.cache), 3)
        Params.log('Prepped cache, position: %s' % self.cache.path, 2)

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

        if port == Params.PORT:
            Params.log("Direct request: %s" % path)
            assert host in LOCALHOSTS, "Cannot service for %s" % host
            self.Response = Response.DirectResponse
            return True
        # XXX: Respond by writing message as plain text, e.g echo/debug it:
        #self.Response = Response.DirectResponse
        # Filter request by regex from patterns.drop
        filtered_path = "%s/%s" % ( host, path )
        m = Rules.Drop.match( filtered_path )
        if m:
            self.set_blocked_response( path )
            Params.log('Dropping connection, '
                        'request matches pattern: %r.' % m, 1)
            return True
        if Params.STATIC and self.cache.full():
            Params.log('Static mode; serving file directly from cache')
            self.cache.open_full()
            self.Response = Response.DataResponse
            return True

    def prepare_nocache_response( self ):
        "Blindly respond for NoCache rule matches. "
        for pattern, compiled in Params.NOCACHE:
            p = self.url.find( ':' ) # find len of scheme-id
            if compiled.match( self.url[p+3:] ):
                Params.log('Not caching request, matches pattern: %r.' %
                    pattern)
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
        return self.cache.size;
    def set_size( self, size ):
        self.cache.size = size
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
#
#    def close(self):
#        return self.cache.close()
#
#    def __del__(self):
#        del self.cache



class HttpProtocol(ProxyProtocol):

    rewrite = None

    def __init__( self, request ):
        host, port = request.hostinfo
        verb, path, proto = request.envelope

        # Calling super constructor
        if self.prepare_direct_response(request):
            # don't initialize cache for direct requests, let response class
            # handle further processing.
            super(HttpProtocol, self).__init__(request, False)
            self.__socket = None
            return
        else:
            # normal caching proxy response
            super(HttpProtocol, self).__init__(request)

        Params.log("Cache partial: %s, full:%s" % (self.cache.partial(),
            self.cache.full()), 3)

        # Prepare request for contact with origin server..
        head = 'GET /%s HTTP/1.1' % path
    
        args = request.headers

        args.pop( 'Accept-Encoding', None )
        htrange = args.pop( 'Range', None )
        assert not htrange,\
                "Req for %s had a range: %s" % (self.url, htrange)

        # if expires < now: revalidate
        # TODO: RFC 2616 14.9.4: Cache revalidation and reload controls
        cache_control = args.pop( 'Cache-Control', None )
        # HTTP/1.0 compat
        #if not cache_control:
        #    cache_control = args.pop( 'Pragma', None )
        #    if cache_control:
        #        assert cache_control.strip() == "no-cache"
        #        args['Cache-Control'] = "no-cache"

        stat = self.cache.partial() or self.cache.full()
        if stat: # and cached_resource
            size = stat.st_size
            mtime = time.strftime(
                Params.TIMEFMT, time.gmtime( stat.st_mtime ) )
            if self.cache.partial():
                Params.log('Requesting resume of partial file in cache: '
                    '%i bytes, %s' % ( size, mtime ))
                args[ 'Range' ] = 'bytes=%i-' % size
                args[ 'If-Range' ] = mtime
            else:#if cache_reload:
                Params.log('Checking complete file in cache: %i bytes, %s' %
                    ( size, mtime ), 1)
                # XXX: treat as unspecified end-to-end revalidation
                # should detect existing cache-validating conditional?
                # FIXME: Validate client validator against cached entry
                args[ 'If-Modified-Since' ] = mtime
        else: 
            # don't gateway conditions, client seems to have cache but this is 
            # a miss for the proxy
            args.pop( 'If-None-Match', None )
            args.pop( 'If-Modified-Since', None )

        # TODO: Store relationship with referer
        relationtype = args.pop('X-Relationship', None)
        referer = args.get('Referer', None)
        if referer:
            #self.descriptors.relate(relationtype, self.url, referer)
            pass

        # Prepare Protocol object for server request
        Params.log("HttpProtocol: Connecting to %s:%s" % request.hostinfo, 2)
        self.__socket = connect(request.hostinfo)
        self.__sendbuf = '\r\n'.join(
            [ head ] + map( ': '.join, args.items() ) + [ '', '' ] )
        self.__recvbuf = ''
        # Prepare to parse server response
        self.__parse = HttpProtocol.__parse_head

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
        Params.log('Server responds '+ line.rstrip(), threshold=1)
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
            Params.log('> '+ line.rstrip(), 2)
            key, value = line.split( ':', 1 )
            if key.lower() in HTTP.Header_Map:
                key = HTTP.Header_Map[key.lower()]
            else:
                Params.log("Warning: %r not a known HTTP (response) header (%r)"% (
                        key,value.strip()), 1)
                key = key.title() # XXX: bad? :)
            if key in self.__args:
              self.__args[ key ] += '\r\n' + key + ': ' + value.strip()
            else:
              self.__args[ key ] = value.strip()
        elif line in ( '\r\n', '\n' ):
            self.__parse = None
        else:
            Params.log('Warning: ignored header line: '+ line)
        return eol

    def recv( self, sock ):

        """"
        The Protocol.recv function processes the server response.
        It reads until headers can be parsed, then determines and prepares 
        Response type. 
        """

        assert not self.hasdata(), "has data"

        chunk = sock.recv( Params.MAXCHUNK, socket.MSG_PEEK )
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

#        assert self.__args.pop( 'Transfer-Encoding', None ) != 'chunked', \
#                "Chunked response: %s %s" % ( self.__status, self.url)

        # Check wether to monitor the response based on the request
        if self.prepare_nocache_response():
            return
   
        # Initialize a facade for the storage and check for existing data
        self.descriptor = Resource.storage.find(self.cache.path)
        if not self.descriptor:
            self.descriptor = Resource.storage.prepare_for_request(
                    self.cache.path, self.request) 

        # Sanity checks
        if self.descriptor and not (self.cache.full() or self.cache.partial()):
            Params.log("Warning: stale descriptor")
            self.descriptor.drop()

        elif not self.descriptor and (self.cache.full() or self.cache.partial()):
            Params.log("Error: stale cache %s" % self.cache.path)
            # XXX: should load new Descriptor into db here or delete stale files.

        # Process and update headers before deferring to response class
        # 2xx
        if self.__status in ( HTTP.OK, HTTP.MULTIPLE_CHOICES ):

            self.recv_entity()
            assert not self.descriptor, \
                "Should not have descriptor for new resource. "
            self.descriptor.init( self.cache.path, self.__args )
            self.set_dataresponse();

        elif self.__status == HTTP.PARTIAL_CONTENT \
                and self.cache.partial():

            self.recv_part()
            assert self.descriptor, \
                "Should have descriptor for partial content. "
            self.descriptor.update( self.__args )
            self.set_dataresponse();

        # 3xx: redirects
        elif self.__status in (HTTP.FOUND, 
                    HTTP.MOVED_PERMANENTLY,
                    HTTP.TEMPORARY_REDIRECT):

# XXX:
            #location = self.__args.pop( 'Location', None )
            if self.descriptor:
                self.descriptor.move( self.cache.path, self.__args )
#            self.cache.remove_partial()
            self.Response = Response.BlindResponse

        elif self.__status == HTTP.NOT_MODIFIED:

            if not self.cache.full():
                Params.log("Warning: Cache miss: %s" % self.url)
                assert not self.cache.partial(), self.cache.path
                self.Response = Response.BlindResponse

            else:
                assert self.descriptor
                self.descriptor.update( self.__args )
                if not self.request.is_conditional():
                    Params.log("Reading complete file from cache at %s" % 
                            self.cache.path)
                    self.cache.open_full()
                    self.Response = Response.DataResponse
                else:
                    self.Response = Response.ProxyResponse

        # 4xx: client error
        elif self.__status in ( HTTP.FORBIDDEN, HTTP.METHOD_NOT_ALLOWED ):

            self.descriptor.set_broken( self.__status )
            self.Response = Response.BlindResponse

        elif self.__status in ( HTTP.NOT_FOUND, HTTP.GONE ):

            self.Response = Response.BlindResponse
            #if self.descriptor:
            #    self.descriptor.update( self.__args )

        elif self.__status in ( HTTP.REQUEST_RANGE_NOT_STATISFIABLE, ):
            if self.cache.partial():
                Params.log("Warning: Cache corrupted?: %s" % self.url)
                self.cache.remove_partial()
            elif self.cache.full():
                self.cache.remove_full()
            if self.descriptor:
                self.descriptor.drop()
                Params.log("Dropped descriptor: %s" % self.url)
            self.Response = Response.BlindResponse

        else:
            Params.log("Warning: unhandled: %s, %s" % (self.__status, self.url))
            self.Response = Response.BlindResponse


    def recv_entity(self):
        """
        Prepare to receive new entity.
        """
        if self.cache.full():
            Params.log("HttpProtocol.recv_entity: overwriting cache: %s" %
                    self.url,4)
            self.cache.remove_full()
            self.cache.open_new()
        else:
            Params.log("HttpProtocol.recv_entity: new cache : %s" %
                    self.url,4)
            self.cache.open_new()
            assert self.cache.partial()
        # FIXME: load http entity, perhaps response headers from shelve
        #self.descriptors.map_path(self.cache.path, uriref)
        #self.descriptors.put(uriref, 
        #descr = self.get_descriptor()
        #self.mtime, self.size = scriptor.last_modified, descr.
        if 'Last-Modified' in self.__args:
            try:
                self.mtime = calendar.timegm( time.strptime(
                    self.__args[ 'Last-Modified' ], Params.TIMEFMT ) )
            except:
                Params.log('Error: illegal time format in Last-Modified: %s.' %
                    self.__args[ 'Last-Modified' ])
                # XXX: Try again, should make a list of alternate (but invalid) date formats
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
                        Params.log('Fatal: unable to parse Last-Modified: %s.' %
                            self.__args[ 'Last-Modified' ])
        if 'Content-Length' in self.__args:
            self.size = int( self.__args[ 'Content-Length' ] )

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
        assert self.cache.partial(), "Missing cache but receiving partial entity. "

    def set_dataresponse(self):
        mediatype = self.__args.get( 'Content-Type', None )
        if Params.PROXY_INJECT and mediatype and 'html' in mediatype:
            Params.log("XXX: Rewriting HTML resource: "+self.url)
            self.rewrite = True
        if self.__args.pop( 'Transfer-Encoding', None ) == 'chunked':
            self.Response = Response.ChunkedDataResponse
        else:
            self.Response = Response.DataResponse

    @property
    def url( self ):
        return self.request.url
    
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
        args = self.response_headers()
        return self.print_message(args)

    def args( self ):
        return self.__args.copy()

    def response_headers( self ):
        args = self.args()

        via = "%s:%i" % (Params.HOSTNAME, Params.PORT)
        if args.setdefault('Via', via) != via:
            args['Via'] += ', '+ via

        return args

    def socket( self ):
        return self.__socket


class FtpProtocol( ProxyProtocol ):

    Response = None

    def __init__( self, request ):
        super(FtpProtocol, self).__init__( request )

        if Params.STATIC and self.cache.full():
          self.__socket = None
          Params.log("Static FTP cache : %s" % self.url)
          self.cache.open_full()
          self.Response = Response.DataResponse
          return

        Params.log("FtpProtocol: Connecting to %s:%s" % request.hostinfo, 2)
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
                Params.log("Unmodified FTP cache : %s" % self.url)
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


