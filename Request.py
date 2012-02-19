import os, socket, time

import Params, Protocol


class HttpRequest:

    Protocol = None

    def __init__( self ):
        self.__parse = self.__parse_head
        self.__recvbuf = ''

    def __parse_head( self, chunk ):

        eol = chunk.find( '\n' ) + 1
        if eol == 0:
          return 0

        line = chunk[ :eol ]
        Params.log('Client sends '+ line.rstrip())
        fields = line.split()
        assert len( fields ) == 3, 'invalid header line: %r' % line
        self.__verb, self.__reqpath, self.__prototag = fields
        self.__args = {}
        self.__parse = self.__parse_args

        return eol

    def __parse_args( self, chunk ):

        eol = chunk.find( '\n' ) + 1
        if eol == 0:
            return 0

        line = chunk[ :eol ]
        if ':' in line:
            Params.log('> '+ line.rstrip(), 1)
            key, value = line.split( ':', 1 )
            key = key.title()
            assert key not in self.__args, 'duplicate key: %s' % key
            self.__args[ key ] = value.strip()
        elif line in ( '\r\n', '\n' ):
            self.__size = int( self.__args.get( 'Content-Length', 0 ) )
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
            Params.log('Ignored header line: %r' % line)

        return eol

    def __parse_body( self, chunk ):

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
                'client closed connection before sending a complete message header'
        self.__recvbuf += chunk
        while self.__parse:
            bytecnt = self.__parse( self.__recvbuf )
            if not bytecnt:
                return
            self.__recvbuf = self.__recvbuf[ bytecnt: ]
        assert not self.__recvbuf, 'client sends junk data after message header'

        if self.__reqpath.startswith( 'http://' ):
            host = self.__reqpath[ 7: ]
            port = 80
            if self.__verb == 'GET':
                self.Protocol = Protocol.HttpProtocol
            else:
                self.Protocol = Protocol.BlindProtocol
        elif self.__reqpath.startswith( 'ftp://' ):
            assert self.__verb == 'GET', '%s request unsupported for ftp' % self.__verb
            self.Protocol = Protocol.FtpProtocol
            host = self.__reqpath[ 6: ]
            port = 21
        else:
            host = self.__reqpath
            port = 8080
        if '/' in host:
            host, path = host.split( '/', 1 )
        else:
            path = ''
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

        # Add Date (as per HTTP/1.1 [RFC 2616] 14.18)
        if 'Date' not in self.__args:
            self.__args[ 'Date' ] = time.strftime(
                Params.TIMEFMT, time.gmtime() )

        # Add proxy Via header (per HTTP1.1 [RFC 2616] 14.45)
        via = "1.1 %s:%i (htcache/0.1)" % (socket.gethostname(), Params.PORT)
        if self.__args.setdefault('Via', via) != via:
            self.__args['Via'] += ', '+ via

    @property
    def hostinfo(self):
        return self.__host, self.__port

    def recvbuf( self ):
        assert self.Protocol, "No protocol yet"
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
        assert self.Protocol, "no protocol"
        return self.__host, self.__port, self.__path

    def args( self ):
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
        return hash(( self.__host, self.__port, self.__path ))

    def __eq__( self, other ):
        assert self.Protocol
        request1 = self.__verb,  self.__host,  self.__port,  self.__path
        request2 = other.__verb, other.__host, other.__port, other.__path
        return request1 == request2

