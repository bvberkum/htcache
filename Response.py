import sys, time, traceback, socket, hashlib
from pprint import pformat

import Params, fiber


class BlindResponse:

    Done = False

    def __init__( self, protocol, request ):

        self.__sendbuf = protocol.recvbuf()

    def hasdata( self ):

        return bool( self.__sendbuf )

    def send( self, sock ):

        assert not self.Done
        bytes = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytes: ]

    def needwait( self ):

        return False

    def recv( self, sock ):

        assert not self.Done
        chunk = sock.recv( Params.MAXCHUNK )
        if chunk:
          self.__sendbuf += chunk
        elif not self.__sendbuf:
          self.Done = True

    def finalize(self, client):
        pass


class DataResponse:

    Done = False

    def __init__( self, protocol, request ):

        self.__protocol = protocol
        self.__pos, self.__end = request.range()
        if self.__end == -1:
            self.__end = self.__protocol.size

        # TODO: on/off: self.__hash = hashlib.sha1()

        try:
            args = self.__protocol.args()
        except:
            args = {}

        if protocol.cache.path in protocol.descriptors:
        #if protocol.has_descriptor():
          descr = protocol.descriptors[protocol.cache.path]
          #descr = protocol.get_descriptor()
          srcrefs, mediatype, charset, languages, features = descr
          Params.log("Descriptor: %s" % pformat(descr))
          # Abuse feature dict to store headers
          # TODO: parse mediatype, charset, language..
          if descr[-1]:
            for k, v in descr[-1].items():
              #if 'encoding' in k.lower(): continue
              args[k] = v
        else:
          Params.log("No descriptor for %s" % protocol.path)

        via = "%s:%i" % (socket.gethostname(), Params.PORT)
        if args.setdefault('Via', via) != via:
            args['Via'] += ', '+ via
        args[ 'Connection' ] = 'close'
        if self.__protocol.mtime >= 0:
            args[ 'Last-Modified' ] = time.strftime( Params.TIMEFMT, time.gmtime( self.__protocol.mtime ) )
        if self.__pos == 0 and self.__end == self.__protocol.size:
            head = 'HTTP/1.1 200 OK'
            if self.__protocol.size >= 0:
                args[ 'Content-Length' ] = str( self.__protocol.size )
        elif self.__end >= 0:
            head = 'HTTP/1.1 206 Partial Content'
            args[ 'Content-Length' ] = str( self.__end - self.__pos )
            if self.__protocol.size >= 0:
                args[ 'Content-Range' ] = 'bytes %i-%i/%i' % ( self.__pos, self.__end - 1, self.__protocol.size )
            else:
                args[ 'Content-Range' ] = 'bytes %i-%i/*' % ( self.__pos, self.__end - 1 )
        else:
            head = 'HTTP/1.1 416 Requested Range Not Satisfiable'
            args[ 'Content-Range' ] = 'bytes */*'
            args[ 'Content-Length' ] = '0'

        Params.log('HTCache responds %s' % head)
        if Params.VERBOSE > 1:
            for key in args:
                Params.log('> %s: %s' % ( key, args[ key ].replace( '\r\n', ' > ' ) ))
        # Prepare response for client
        self.__sendbuf = '\r\n'.join( [ head ] + map( ': '.join, args.items() ) + [ '', '' ] )
        if Params.LIMIT:
            self.__nextrecv = 0

    def hasdata( self ):

        if self.__sendbuf:
            return True
        elif self.__pos >= self.__protocol.tell():
            return False
        elif self.__pos < self.__end or self.__end == -1:
            return True
        else:
            return False

    def send( self, sock ):

        assert not self.Done
        if self.__sendbuf:
            bytes = sock.send( self.__sendbuf )
            self.__sendbuf = self.__sendbuf[ bytes: ]
        else:
            bytes = Params.MAXCHUNK
            if 0 <= self.__end < self.__pos + bytes:
                bytes = self.__end - self.__pos
            chunk = self.__protocol.read( self.__pos, bytes )
            try:
                self.__pos += sock.send( chunk )
            except:
                Params.log("Error writing to client, aborted!")  
                self.Done = True
                # Unittest 2: keep partial file 
                #if not self.__protocol.cache.full():
                #    self.__protocol.cache.remove_partial()
                return
        self.Done = not self.__sendbuf and ( self.__pos >= self.__protocol.size >= 0 or self.__pos >= self.__end >= 0 )

        # XXX: store hash for new recv'd content
        #if self.Done: print 'hash', self.__hash.hexdigest()

    def needwait( self ):

        return Params.LIMIT and max( self.__nextrecv - time.time(), 0 )

    def recv( self, sock ):

        assert not self.Done
        chunk = sock.recv( Params.MAXCHUNK )
        if chunk:
            self.__protocol.write( chunk )
            #self.__hash.update( chunk )
            if Params.LIMIT:
                self.__nextrecv = time.time() + len( chunk ) / Params.LIMIT
        else:
            if self.__protocol.size >= 0:
                assert self.__protocol.size == self.__protocol.tell(), 'connection closed prematurely'
            else:
                self.__protocol.size = self.__protocol.tell()
                Params.log('Connection closed at byte %i' % self.__protocol.size)
            self.Done = not self.hasdata()

    def finalize(self, client):
        pass


class ChunkedDataResponse( DataResponse ):

    def __init__( self, protocol, request ):
        DataResponse.__init__( self, protocol, request )
        self.__protocol = protocol
        self.__recvbuf = ''

    def recv( self, sock ):
        assert not self.Done
        chunk = sock.recv( Params.MAXCHUNK )
        assert chunk, 'chunked data error: connection closed prematurely'
        self.__recvbuf += chunk
        while '\r\n' in self.__recvbuf:
            head, tail = self.__recvbuf.split( '\r\n', 1 )
            chunksize = int( head.split( ';' )[ 0 ], 16 )
            if chunksize == 0:
                self.__protocol.size = self.__protocol.tell()
                Params.log('Connection closed at byte %i' % self.__protocol.size)
                self.Done = not self.hasdata()
                return
            if len( tail ) < chunksize + 2:
                return
            assert tail[ chunksize:chunksize+2 ] == '\r\n', 'chunked data error: chunk does not match announced size'
            Params.log('Received %i byte chunk' % chunksize, 1)
            self.__protocol.write( tail[ :chunksize ] )
            self.__recvbuf = tail[ chunksize+2: ]

class BlockedContentResponse:

    Done = False

    def __init__(self, status, request):
        self.__sendbuf = "HTTP/1.1 OK\r\nContent-Type: text/html\r\n\r\n" +\
                open(Params.HTML_PLACEHOLDER).read() % { 
                        'host': socket.gethostname(), 
                        'port': Params.PORT,
                        'location': '%s:%i/%s' % request.url(),
                        'software': 'htcache/0.1' }

    def hasdata( self ):
        return bool( self.__sendbuf )

    def send( self, sock ):
        assert not self.Done
        bytes = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytes: ]
        if not self.__sendbuf:
            self.Done = True

    def needwait( self ):
        return False

    def recv( self ):
        raise AssertionError

    def finalize(self, client):
        pass

class BlockedImageContentResponse:

    Done = False

    def __init__(self, status, request):
        data = open(Params.IMG_PLACEHOLDER).read()
        self.__sendbuf = "HTTP/1.1 OK\r\nContent-Length: %i\r\n'\
                'Content-Type: image/png\r\n\r\n%s" % (
                len(data), data)

    def hasdata( self ):
        return bool( self.__sendbuf )

    def send( self, sock ):
        assert not self.Done
        bytes = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytes: ]
        if not self.__sendbuf:
            self.Done = True

    def needwait( self ):
        return False

    def recv( self ):
        raise AssertionError

    def finalize(self, client):
        pass


class DirectResponse:

    """
    Echo request header in response body.
    """

    Done = False

    urlmap = {
        'reload': 'reload_proxy',
    }

    def __init__( self, protocol, request ):
        path = request.url()[2]
        self.action = None

        if path in self.urlmap:
            self.action = self.urlmap[path]
            getattr(self, self.action)()
        else:
            lines = [ 'HTCache: %s' % path, '', 'Requesting:' ]
            head, body = request.recvbuf().split( '\r\n\r\n', 1 )
            for line in head.splitlines():
                lines.append( len( line ) > 78 and '  %s...' % line[ :75 ] or '  %s' % line )
            if body:
                lines.append( '+ Body: %i bytes' % len( body ) )

            lines.append( pformat(sys.exc_info()) )
            lines.append( pformat(request.url()) )

            #if sys.exc_info() != None, None, None:
            #    lines.append( 'Exception:' )
            #    lines.append( traceback.format_exc() )
            #    lines.append( '' )
            #else:
            #    lines.append( '' )
            #    lines.append( '' )

            #lines.append( "".join(traceback.format_stack()) )
            #lines.append( '' )
            self.__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/plain\r\n\r\n%s' % ( protocol, '\n'.join( lines ) )
     
    def reload_proxy(self):
        self.prepare_response("200 OK", "Restarting gateway")

    def prepare_response(self, status, msg):
        if isinstance(msg, list):
            lines = msg
        else:
            lines = [msg]
        self.__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/plain\r\n\r\n%s' % (
                status, '\n'.join( lines ) )

    def hasdata( self ):
        return bool( self.__sendbuf )

    def send( self, sock ):
        assert not self.Done
        bytes = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytes: ]
        if not self.__sendbuf:
            self.Done = True

    def finalize(self, client):
        if self.action == 'reload_proxy':
            client.close()
            raise fiber.Restart()

    def needwait( self ):
        return False

    def recv( self ):
        raise AssertionError


class NotFoundResponse( DirectResponse ):

    def __init__( self, protocol, request ):
        DirectResponse.__init__( self, '404 Not Found', request )


class ExceptionResponse( DirectResponse ):

    def __init__( self, request ):
        traceback.print_exc()
        DirectResponse.__init__( self, '500 Internal Server Error', request )

