import hashlib, socket, time, traceback, urlparse, urllib

import fiber
import Params, Resource, Rules, HTTP, Runtime


class BlindResponse:

    """
    Like BlindProtocol, BlindResponse tries for graceful
    recovery in unexpected protocol situations.
    """

    Done = False

    def __init__( self, protocol, request ):

        if hasattr(protocol, 'responsebuf'):
            self.__sendbuf = protocol.responsebuf()
        else:
            self.__sendbuf = protocol.recvbuf()

    def hasdata( self ):

        return bool( self.__sendbuf )

    def send( self, sock ):

        assert not self.Done
        bytecnt = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytecnt: ]

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


class ProxyResponse(BlindResponse):

    pass


class DataResponse:

    Done = False
    content_rewrite = []

    def __init__( self, protocol, request ):

        Params.log("New DataResponse for "+str(request.url), 5)

        self.__protocol = protocol
        self.__pos, self.__end = request.range()
        if self.__end == -1:
            self.__end = self.__protocol.size

        # TODO: on/off: 
        #if protocol.capture:
        #    self.__hash = hashlib.sha1()

        args = protocol.response_headers()

        cached_headers = {}
        if protocol.descriptor:
            pass
        #  Params.log("Descriptor: %s" % pformat(descr))
            #urirefs, cached_args = protocol.get_descriptor()
          # Abuse feature dict to store headers
          # TODO: parse mediatype, charset, language..
          #if descr[-1]:
          #  for k, v in descr[-1].items():
          #    #if 'encoding' in k.lower(): continue
          #    args[k] = v
        #else:
        #  Params.log("No descriptor for %s" % protocol.cache.path)
# XXX: this may need to be on js serving..
#        if self.__protocol.rewrite:
#            args['Access-Control-Allow-Origin'] = "%s:%i" % request.hostinfo

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

        Params.log('HTCache responds %s' % head, threshold=1)
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
            bytecnt = sock.send( self.__sendbuf )
            self.__sendbuf = self.__sendbuf[ bytecnt: ]
        else:
            bytecnt = Params.MAXCHUNK
            if 0 <= self.__end < self.__pos + bytecnt:
                bytecnt = self.__end - self.__pos

            chunk = self.__protocol.read( self.__pos, bytecnt )
            if self.__protocol.rewrite:
                delta, chunk = Rules.Rewrite.run(chunk)
                self.__protocol.size += delta
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
                Params.log('Connection closed at byte %i' % self.__protocol.size, threshold=2)
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
                Params.log('Connection closed at byte %i' % self.__protocol.size, threshold=2)
                self.Done = not self.hasdata()
                return
            if len( tail ) < chunksize + 2:
                return
            assert tail[ chunksize:chunksize+2 ] == '\r\n', \
                    'chunked data error: chunk does not match announced size'
            Params.log('Received %i byte chunk' % chunksize, threshold=1)
            self.__protocol.write( tail[ :chunksize ] )
            self.__recvbuf = tail[ chunksize+2: ]


class BlockedContentResponse:

    Done = False

    def __init__(self, status, request):
        url = request.hostinfo + (request.envelope[1],)
        self.__sendbuf = "HTTP/1.1 403 Dropped By Proxy\r\n'\
                'Content-Type: text/html\r\n\r\n"\
                + open(Params.HTML_PLACEHOLDER).read() % { 
                        'host': Params.HOSTNAME,
                        'port': Params.PORT,
                        'location': '%s:%i/%s' % url,
                        'software': 'htcache/%s' % Params.VERSION }

    def hasdata( self ):
        return bool( self.__sendbuf )

    def send( self, sock ):
        assert not self.Done
        bytecnt = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytecnt: ]
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
        bytecnt = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytecnt: ]
        if not self.__sendbuf:
            self.Done = True

    def needwait( self ):
        return False

    def recv( self ):
        raise AssertionError

    def finalize(self, client):
        pass


class DirectResponse:

    Done = False

    """
    HTCache generated response for request directly to 
    proxy port.
    """

    urlmap = {
        'control': 'control_proxy',
        'reload': 'reload_proxy',
        'dhtml.css': 'serve_stylesheet',
        'dhtml.js': 'serve_script',
        'echo': 'serve_echo',
        'page-info': 'serve_descriptor',
        'info': 'serve_params',
        'browse': 'serve_frame',
        'downloads': 'serve_downloads',
        'list': 'serve_list',
    }

    def __init__( self, protocol, request, status='200 Okeydokey, here it comes', path=None):
        if status[0] == '2':
            path = protocol.reqname
            if '?' in path:
                path = path.split('?')[0]
            if path not in self.urlmap:
                status = '404 No such resource'
                path = 'echo'
        else:
            path = 'echo'
        self.action = self.urlmap[path]
        getattr(self, self.action)(status, protocol, request)

    def serve_list(self, status, protocol, request):
        self.prepare_response(
                "200 OK", 
                "# Downloads \n" 
                "" + ('\n'.join(map(str,Runtime.DOWNLOADS.keys())))
            )

    def serve_downloads(self, status, protocol, request):
        self.prepare_response(
                "200 OK", 
                "No data for %r %r %r %r"%request.url
            )

    def serve_echo(self, status, protocol, request):
        lines = [ 'HTCache: %s' % status, '' ]
        
        lines.append( 'Request echo ing:' )
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

        self.__sendbuf = "HTTP/1.1 %s\r\n"\
            "Access-Control-Allow-Origin: *\r\n"\
            "Content-Type: text/plain\r\n"\
            "\r\n%s" % ( status, '\n'.join( lines ) )
      
    def control_proxy(self, status, protocol, request):
        head, body = request.recvbuf().split( '\r\n\r\n', 1 )
        req = { 
                'args': request.headers
            }
        if body:
            try:
                req = Params.json_read(body)
            except:
                #print "JSON: ",request.recvbuf()
                raise
        # TODO: echos only
        self.prepare_response(status, 
                Params.json_write(req), mime="application/json")

    def reload_proxy(self, status, protocol, request):
        self.prepare_response(status, "Reloading gateway")

    def serve_stylesheet(self, status, protocol, request):
        cssdata = open(Params.PROXY_INJECT_CSS).read()
        self.__sendbuf = "\r\n".join( [ 
            "HTTP/1.1 %s" % status,
            "Content-Type: text/css\r\n",
            cssdata
        ])

    def serve_frame(self, status, protocol, request):
        status = '200 Have A Look'
        host = "%s:%s" % request.hostinfo
        uri = '?'.join(request.envelope[1].split('?')[1:])
        lines = [
            '<html>',
            '<head><title>HTCache browser</title>',
            '<link rel="stylesheet" type="text/css" href="http://'+host+'/htcache.css" />',
            '</head>',
            '<body id="htcache-browse">',
            '<pre>',
            '</pre>',
            '<iframe src="'+uri+'" />',
            '</body>',
            '</html>']

        self.__sendbuf = 'HTTP/1.1 %s\r\nContent-Type: text/html\r\n'\
                '\r\n%s' % ( status, '\n'.join( lines ) )

    def serve_params(self, status, protocol, request):
        msg = Params.format_info()
        self.prepare_response(status, msg, mime='application/json')

    def serve_descriptor(self, status, protocol, request):
        q = urlparse.urlparse( request.url[3] )[4]
        url = urlparse.urlparse(urllib.unquote(q[4:]))

        if ':' in url[1]:
            hostinfo = url[1].split(':')
            hostinfo[1] = int(hostinfo[1])
        else:
            hostinfo = url[1], 80
        cache = Resource.get_cache(hostinfo, url[2][1:]) 
        descriptors = Resource.get_backend()
        if cache.path in descriptors:
            descr = descriptors[cache.path]
            self.prepare_response(status, 
                    Params.json_write(descr), 
                    mime='application/json')
        else:
            self.prepare_response("404 No Data", "No data for %s %s %s %s"%request.url)

    def serve_script(self, status, protocol, request):
        jsdata = open(Params.PROXY_INJECT_JS).read()
        self.__sendbuf = "\r\n".join( [ 
            "HTTP/1.1 %s" % status,
            "Content-Type: application/javascript\r\n"
            "Access-Control-Allow-Origin: *\r\n",
            jsdata
        ])

    def prepare_response(self, status, msg, mime='text/plain'):
        if isinstance(msg, list):
            lines = msg
        else:
            lines = [msg]
        headers = "Access-Control-Allow-Origin: *\r\nContent-Type: "+mime+"\r\n"
        self.__sendbuf = 'HTTP/1.1 %s\r\n%s'\
                '\r\n%s' % ( status, headers, '\n'.join( lines ) )

    def hasdata( self ):
        return bool( self.__sendbuf )

    def send( self, sock ):
        assert not self.Done
        bytecnt = sock.send( self.__sendbuf )
        self.__sendbuf = self.__sendbuf[ bytecnt: ]
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
        if request.url()[0] == 'ftp':
            DirectResponse.__init__( self, 
                    protocol, request,
                    status='550 Not Found'
                )
        elif request.url()[0] == 'http':
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


