import hashlib, socket, time, traceback

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
    content_rewrite = []

    def __init__( self, protocol, request ):

        self.__protocol = protocol
        self.__pos, self.__end = request.range()
        if self.__end == -1:
            self.__end = self.__protocol.size

        # TODO: on/off: 
        #if protocol.capture:
        #    self.__hash = hashlib.sha1()

        args = self.__protocol.args()

        cached_headers = {}
        if protocol.has_descriptor():
            #Params.log(protocol.get_descriptor())
            urls, mediatype, charset, languages, metadata, features = \
                    protocol.get_descriptor()
            cached_headers = metadata
            #urirefs, cached_args = protocol.get_descriptor()
            #Params.log(descr)
          # Abuse feature dict to store headers
          # TODO: parse mediatype, charset, language..
          #if descr[-1]:
          #  for k, v in descr[-1].items():
          #    #if 'encoding' in k.lower(): continue
          #    args[k] = v
        #else:
        #  Params.log("No descriptor for %s" % protocol.path)
        #srcrefs, mediatype, charset, languages, features = protocol.get_descriptor()

        via = "%s:%i" % (socket.gethostname(), Params.PORT)
        if args.setdefault('Via', via) != via:
            args['Via'] += ', '+ via
        args[ 'Connection' ] = 'close'
        if self.__protocol.mtime >= 0:
            args[ 'Last-Modified' ] = time.strftime( Params.TIMEFMT, \
                    time.gmtime( self.__protocol.mtime ) )

        if self.__pos == 0 and self.__end == self.__protocol.size:
            head = 'HTTP/1.1 200 OK'
            if self.__protocol.size >= 0:
                args[ 'Content-Length' ] = str( self.__protocol.size )
            if 'Content-Type' in cached_headers:
                args['Content-Type'] = cached_headers['Content-Type']
            #for regex, repl in Params.REWRITE:
            #    print "Replace", repl
            #    if regex.match(mediatype):
            #        self.content_rewrite.append(regex, repl)
            #        print "Rewriting HTML using %r, %r" % (regex, repl)
            #        self.__args.pop('Content-MD5', None)
            #        self.size += len(repl)
            #        self.__args['Content-Length'] = self.size
            #        break
        elif self.__end >= 0:
            head = 'HTTP/1.1 206 Partial Content'
            args[ 'Content-Length' ] = str( self.__end - self.__pos )
            if self.__protocol.size >= 0:
                args[ 'Content-Range' ] = 'bytes %i-%i/%i' % ( 
                        self.__pos, self.__end - 1, self.__protocol.size )
            else:
                args[ 'Content-Range' ] = 'bytes %i-%i/*' % ( 
                        self.__pos, self.__end - 1 )
        else:
            head = 'HTTP/1.1 416 Requested Range Not Satisfiable'
            args[ 'Content-Range' ] = 'bytes */*'
            args[ 'Content-Length' ] = '0'

        Params.log('HTCache responds %s' % head)
        if Params.VERBOSE > 1:
            for key in args:
                Params.log('> %s: %s' % ( 
                    key, args[ key ].replace( '\r\n', ' > ' ) ), 2)

        # Prepare response for client
        self.__sendbuf = '\r\n'.join( [ head ] + 
                map( ': '.join, args.items() ) + [ '', '' ] )
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
        self.Done = not self.__sendbuf and ( 
                self.__pos >= self.__protocol.size >= 0 
                or self.__pos >= self.__end >= 0 )

        # TODO: store hash for new recv'd content
        #if self.__protocol.capture and self.Done: 
        #    print 'hash', self.__hash.hexdigest()

    def needwait( self ):

        return Params.LIMIT and max( self.__nextrecv - time.time(), 0 )

    def recv( self, sock ):
        """
        Read chuck from server response. Hash or rewrite if needed.
        """

        assert not self.Done
        chunk = sock.recv( Params.MAXCHUNK )
        if chunk:
            self.__protocol.write( chunk )
            #if self.__protocol.capture:
            #    self.__hash.update( chunk )
            if Params.LIMIT:
                self.__nextrecv = time.time() + len( chunk ) / Params.LIMIT
        else:
            if self.__protocol.size >= 0:
                assert self.__protocol.size == self.__protocol.tell(), \
                        'connection closed prematurely'
            else:
                self.__protocol.size = self.__protocol.tell()
                Params.log('Connection closed at byte %i' % self.__protocol.size)
            self.Done = not self.hasdata()

        #if self.Done:
        #    for pattern, substitute in self.content_rewrite:
        #    	self.__protocol.write( substitute )
                #chunk, count = pattern.subn(substitute, chunk)
                #self.size += len(substitute)
                #(count * len(substitute))
                #Params.log("Rewritten content with %r, %i times" % (
                #        (pattern, substitute), count))

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
            assert tail[ chunksize:chunksize+2 ] == '\r\n', \
                    'chunked data error: chunk does not match announced size'
            Params.log('Received %i byte chunk' % chunksize, 1)
            self.__protocol.write( tail[ :chunksize ] )
            self.__recvbuf = tail[ chunksize+2: ]

class BlockedContentResponse:

    Done = False

    def __init__(self, status, request):
        url = request.hostinfo + (request.envelope[1],)
        self.__sendbuf = "HTTP/1.1 403 Dropped By Proxy\r\n'\
                'Content-Type: text/html\r\n\r\n"\
                + open(Params.HTML_PLACEHOLDER).read() % { 
                        'host': socket.gethostname(), 
                        'port': Params.PORT,
                        'location': '%s:%i/%s' % url,
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
        self.__sendbuf = 'HTTP/1.1 403 Dropped By Proxy\r\n'\
                'Content-Length: %i\r\n'\
                'Content-Type: image/png\r\n\r\n%s' % (
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
    HTCache generated response for request directly to 
    proxy port.
    """

    Done = False

    urlmap = {
        'reload': 'reload_proxy',
        'js-menu': 'serve_js_menu',
        'echo': 'serve_echo',
        'page-info': 'serve_info',
        'info': 'serve_params',
    }

    def __init__( self, protocol, request, status='200 Okeydokey, here it comes'):
        path = request.envelope[1]
        if path not in self.urlmap:
            status = '404 No such resource'
            path = 'echo'

        self.action = self.urlmap[path]
        getattr(self, self.action)(status, protocol, request)

    def serve_echo(self, status, protocol, request):
        lines = [ 'HTCache: %s' % status, '' ]
        
        lines.append( 'Requesting:' )
        lines.append( '' )

        head, body = request.recvbuf().split( '\r\n\r\n', 1 )
        for line in head.splitlines():
            lines.append( len( line ) > 78 and '  %s...' % 
                    line[ :75 ] or '  %s' % line )
        if body:
            lines.append( '+ Body: %i bytes' % len( body ) )

        lines.append( '' )
        if protocol and protocol.has_response():
            lines.append( '(Partial) Response:' )
            lines.append( '' )
            head, body = protocol.recvbuf().split( '\r\n\r\n', 1 )
            for line in head.splitlines():
                lines.append( len( line ) > 78 and '  %s...' % 
                        line[ :75 ] or '  %s' % line )
            lines.append( '' )

        lines.append( traceback.format_exc() )

        self.__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/plain\r\n'\
                '\r\n%s' % ( status, '\n'.join( lines ) )
      
    def reload_proxy(self, status, protocol, request):
        self.prepare_response(status, "Reloading gateway")
       
    def serve_params(self, status, protocol, request):
        msg = Params.format_info()
        self.prepare_response(status, msg)

    def serve_js_menu(self, status, protocol, request):
        jsdata = open(Params.PROXY_INJECT_JS).read()
        self.__sendbuf = "\r\n".join( [ 
            "HTTP/1.1 %s" % status,
            "Content-Type: application/javascript\r\n",
            jsdata
        ])

    def prepare_response(self, status, msg):
        if isinstance(msg, list):
            lines = msg
        else:
            lines = [msg]
        self.__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/plain\r\n'\
                '\r\n%s' % ( status, '\n'.join( lines ) )

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
        DirectResponse.__init__( self, 
                protocol, request,
                status='404 Not Found'
            )


class ExceptionResponse( DirectResponse ):

    def __init__( self, protocol, request ):
        traceback.print_exc()
        DirectResponse.__init__( self, 
                protocol, request,
                status='500 Internal Server Error'
            )


