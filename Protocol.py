import calendar, os, time, socket, re

import Params, Response, Resource, Cache, Rules
from HTTP import HTTP


class DNSLookupException(Exception):
    def __init__(self, addr, exc):
        self.addr = addr
        self.exc = exc
    def __str__(self):
        return "DNS lookup error for %s: %s" % (self.addr, self.exc)


LOCALHOSTS = ('localhost',socket.gethostname(),'127.0.0.1','127.0.1.1')
DNSCache = {}

def connect( addr ):
    assert Params.ONLINE, 'operating in off-line mode'
    if addr not in DNSCache:
        Params.log('Requesting address info for %s:%i' % addr, 2)
        try:
            DNSCache[ addr ] = socket.getaddrinfo(
                addr[ 0 ], addr[ 1 ], Params.FAMILY, socket.SOCK_STREAM )
        except Exception, e:
            raise DNSLookupException(addr, e)
    family, socktype, proto, canonname, sockaddr = DNSCache[ addr ][ 0 ]
    Params.log('Connecting to %s:%i' % sockaddr,3)
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
        self.__socket = connect(request.hostinfo)
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
    capture = None
    "Wether to track additional metadata for resource"

    def __init__(self, request, prepcache=True):
        "Determine and open cache location, get descriptor backend. "
        super(CachingProtocol, self).__init__()

        self.request = request

        # Track server response
        self.__status, self.__message = None, None

        if not prepcache:
            return

        self.cache = Resource.get_cache(request.hostinfo, request.envelope[1])

        # Get descriptor storage reference
        self.descriptors = Resource.get_backend()

        #if self.has_descriptor() and not (self.cache.full() or
        #        self.cache.partial()):
        #    pass#del self.descriptors[self.cache.path]
        #    #Params.log("Removed stale descriptor")

    def has_response(self):
        return self.__status and self.__message
        
    def has_descriptor(self):
        return self.cache.path in self.descriptors \
                and isinstance(self.get_descriptor(), tuple)

    def get_descriptor(self):
        return self.descriptors[self.cache.path]

    def prepare_direct_response(self, request):
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
        filtered_path = "%s/%s" % (host, path)
        m = Rules.Drop.match(filtered_path)
        if m:
            self.set_blocked_response(path)
            Params.log('Dropping connection, '
                        'request matches pattern: %r.' % m,1)
            return True
        if Params.STATIC and self.cache.full():
            Params.log('Static mode; serving file directly from cache')
            self.cache.open_full()
            self.Response = Response.DataResponse
            return True

    def prepare_nocache_response(self):
        "Blindly respond for NoCache rule matches. "
        for pattern, compiled in Params.NOCACHE:
            p = self.requri.find(':') # split scheme
            if compiled.match(self.requri[p+3:]):
                Params.log('Not caching request, matches pattern: %r.' %
                    pattern)
                self.Response = Response.BlindResponse
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





class HttpProtocol(CachingProtocol):

    rewrite = None

    def __init__( self, request ):
        host, port = request.hostinfo
        verb, path, proto = request.envelope

        # Prepare requri to identify request
        if port != 80:
            hostinfo = "%s:%s" % (host, port)
        else:
            hostinfo = host
        self.requri = "http://%s/%s" %  (hostinfo, path)

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

        # Prepare request for contact with origin server..
        head = 'GET /%s HTTP/1.1' % path
    
        args = request.headers

        args.pop( 'Accept-Encoding', None )
        htrange = args.pop( 'Range', None )
        assert not htrange,\
                "Req for %s had a range: %s" % (self.requri, htrange)

        # if expires < now: revalidate
        # RFC 2616 14.9.4: Cache revalidation and reload controls
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
            #self.descriptors.relate(relationtype, self.requri, referer)
            pass

        #Params.log("HttpProtocol: Connecting to %s:%s" % request.hostinfo, 2)
        Params.log("Connecting to %s:%s" % request.hostinfo,2)
        self.__socket = connect(request.hostinfo)
        self.__sendbuf = '\r\n'.join(
            [ head ] + map( ': '.join, args.items() ) + [ '', '' ] )
        self.__recvbuf = ''
        self.__parse = HttpProtocol.__parse_head

    def hasdata( self ):
        return bool( self.__sendbuf )

    def send( self, sock ):
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
                Params.log("Warning: %r not a known HTTP (response) header (%r)"% (key,value.strip()), 1)
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
        Response type. Once this is available fiber initializes it and
        to it.
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

        if self.prepare_nocache_response():
            return

        mediatype = self.__args.get('Content-Type', None)
        if Params.PROXY_INJECT and mediatype and 'html' in mediatype:
            Params.log("XXX: Rewriting HTML resource: "+self.requri)
            self.rewrite = True

        # Process and update headers before deferring to response class
        # 2xx
        if self.__status in (HTTP.OK, HTTP.MULTIPLE_CHOICES):

            self.recv_entity()
            self.resp_data();

        elif self.__status == HTTP.PARTIAL_CONTENT \
                and self.cache.partial():

            self.recv_part()
            self.resp_data();

        # 3xx: redirects
        elif self.__status == HTTP.NOT_MODIFIED:
                #HTTP.MOVED_PERMANENTLY, HTTP.FOUND, ):
                #location = self.__args['Location']

            if not self.cache.full():
                Params.log("Warning: Cache miss: %s" % self.requri)
                assert not self.cache.partial(), self.cache.path
                self.Response = Response.BlindResponse
            else:
                Params.log("Reading complete file from cache at %s" % 
                        self.cache.path)
                self.cache.open_full()
                self.Response = Response.DataResponse

        # 4xx: client error
        elif self.__status in ( HTTP.FORBIDDEN, ):
            Params.log("TODO: record forbidden")
            self.Response = Response.BlindResponse

        elif self.__status in ( HTTP.REQUEST_RANGE_NOT_STATISFIABLE, ):
            if self.cache.partial():
                Params.log("Warning: Cache corrupted?: %s" % self.requri)
                self.cache.remove_partial()
            elif self.cache.full():
                self.cache.remove_full()
            self.Response = Response.BlindResponse

        elif self.__status in (HTTP.FOUND, 
                    HTTP.MOVED_PERMANENTLY,
                    HTTP.TEMPORARY_REDIRECT):

# XXX:
#            self.cache.remove_partial()
            self.Response = Response.BlindResponse
#            if isinstance(self.request.resource, (Variant, Invariant)):
#                print 'Variant resource has moved'
#            #elif isinstance(self.request.resource, Resource):
#            #    print 'Resource has moved'
#            elif isinstance(self.request.resource, Relocated):
#                print 'Relocated has moved'

#            self.request.resource.update(
#                    status=self.__status, 
#                    **map_headers_to_resource(self.__args))

        else:
            Params.log("Warning: unhandled: %s, %s" % (self.__status, self.requri))
            self.Response = Response.BlindResponse

        assert self.__args.pop( 'Transfer-Encoding', None ) != 'chunked', \
                "Chunked response: %s %s" % (self.__status, self.requri)

        # Cache headers
        # XXX:
#        if self.__status in (HTTP.OK, HTTP.PARTIAL_CONTENT):
        if self.cache.full() or self.cache.partial():#cached_resource:
            pass # TODO: self.descriptors.map_path(self.cache.path, uriref)
            #httpentityspec = Resource.HTTPEntity(self.__args)
            #self.descriptors.put(uriref, httpentityspec.toMetalink())
            self.descriptors[self.cache.path] = [self.requri], self.__args

    def recv_entity(self):
        """
        Prepare to receive new entity.
        """
        if self.cache.full():
            Params.log("HttpProtocol.recv_entity: overwriting cache: %s" %
                    self.requri,4)
            self.cache.remove_full()
            self.cache.open_new()
        else:
            Params.log("HttpProtocol.recv_entity: new cache : %s" %
                    self.requri,4)
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

    def resp_data(self):
        if self.__args.pop( 'Transfer-Encoding', None ) == 'chunked':
            self.Response = Response.ChunkedDataResponse
        else:
            self.Response = Response.DataResponse


    def recvbuf( self ):
        return '\r\n'.join(
            [ 'HTTP/1.1 %i %s' % ( self.__status, self.__message ) ] +
            map( ': '.join, self.__args.items() ) + [ '', '' ] )

    def args( self ):
        return self.__args.copy()

    def socket( self ):
        return self.__socket


class FtpProtocol( CachingProtocol ):

    Response = None

    def __init__( self, request ):
        super(FtpProtocol, self).__init__( request )

        if Params.STATIC and self.cache.full():
          self.__socket = None
          Params.log("Static FTP cache : %s" % self.requri)
          self.cache.open_full()
          self.Response = Response.DataResponse
          return

        self.__socket = connect(request.hostinfo)
        self.__path = request.Resource.ref.path
        self.__path_old = request.envelope[1] # XXX
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
                Params.log("Unmodified FTP cache : %s" % self.requri)
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


