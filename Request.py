import os, socket, time

import Params, Protocol, Resource
from Protocol import HTTP
# FIXME from HTTP import HTTP



class HttpRequest:

    Protocol = None

    def __init__( self ):
        self.__parse = self.__parse_head
        self.__recvbuflen = 0
        self.__recvbuf = ''

    def __parse_head( self, chunk ):
        """
        Start parsing request by splitting the envelope or request line,
        defer to __parse_args.
        """

        eol = chunk.find( '\n' ) + 1
        if eol == 0:
          return 0

        line = chunk[ :eol ]
        Params.log('Client sends '+ line.rstrip(), threshold=1)
        fields = line.split()
        assert len( fields ) == 3, 'invalid header line: %r' % line
        self.__verb, self.__reqpath, self.__prototag = fields
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
                Params.log("Warning: %r not a known HTTP (request) header"% key, 1)
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
        Receive request, parsing header and option body, then determine
        Resource, and prepare Protocol for relaying the request to the content
        origin server.
        """

        assert not self.Protocol, "Cant have protocol"

        chunk = sock.recv( Params.MAXCHUNK )
        assert chunk, \
                'client closed connection before sending a '\
                'complete message header at %s, ' \
                'parser: %r, data: %r' % (self.__recvbuflen, self.__parse, self.__recvbuf)
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

        # Accept http and ftp proxy requests
        if self.__reqpath.startswith( 'http://' ):
            host = self.__reqpath[ 7: ]
            port = 80
            if self.__verb == 'GET':
                self.Protocol = Protocol.HttpProtocol
            else:
                self.Protocol = Protocol.BlindProtocol
        elif self.__reqpath.startswith( 'ftp://' ):
            assert self.__verb == 'GET', \
                    '%s request unsupported for ftp' % self.__verb
            self.Protocol = Protocol.FtpProtocol
            host = self.__reqpath[ 6: ]
            port = 21
        # Accept static requests, and further parse host
        else:
            self.Protocol = Protocol.BlindProtocol
            scheme = ''
            port = 8080

        if scheme: # if proxied URL
            if '/' in host:
                host, path = host.split( '/', 1 )
            else:
                path = ''
            if ':' in host:
                hostinfo = host
                host, port = host.split( ':' )
                port = int( port )
            else:
                hostinfo = "%s:%s" % (host, port)

        self.__host = host
        self.__port = port
        self.__reqpath = path

# FIXME: new dev comment
        # TODO: keep entity headers, strip other message headers from args
        #Params.log('href %s'% proxied_url)
        #self.Resource = Resource.Resource(proxied_url, self.args())

# FIXME: old master
#        req_url = "%s://%s/%s" % (scheme, hostinfo, path)
#        self.resource = Resource.forRequest(req_url)
#
#        if not self.resource:
#            self.resource = Resource.new(req_url)
#        
#        if Params.VERBOSE > 1:
#            print 'Matched to resource', req_url
#        
#        if self.resource and 'Host' not in self.__headers:
#            # Become HTTP/1.1 compliant
#            self.__headers['Host'] = self.resource.ref.host
#
        self.__headers[ 'Host' ] = host
        self.__headers[ 'Connection' ] = 'close'

        self.__headers.pop( 'Keep-Alive', None )
        self.__headers.pop( 'Proxy-Connection', None )
        self.__headers.pop( 'Proxy-Authorization', None )

        # Add Date (as per HTTP/1.1 [RFC 2616] 14.18)
        if 'Date' not in self.__headers:
            self.__headers[ 'Date' ] = time.strftime(
                Params.TIMEFMT, time.gmtime() )

        # Add proxy Via header (per HTTP/1.1 [RFC 2616] 14.45)
        via = "1.1 %s:%i (htcache/%s)" % (socket.gethostname(), Params.PORT,
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

    @property
    def hostinfo(self):
        # XXX: return self.resource.location.host, self.resource.location.port
        return self.__host, self.__port

    @property
    def envelope(self):
        # XXX: used before protocol is determined,  assert self.Protocol
        return self.__verb, self.__reqpath, self.__prototag
        # XXX: return self.__verb.upper(), self.__reqpath, self.__prototag.upper()

    @property
    def url(self):
        return self.__host, self.__port, self.__reqpath

    @property
    def headers(self):
        # XXX: used before protocol is determined,  assert self.Protocol
        assert self.Protocol, "Request has no protocol"
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
        return "<HttpRequest %s, %s>" % (self.hostinfo, self.envelope)

