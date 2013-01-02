import sys, os, select, time, socket, traceback

import Params
from util import log


class Restart(Exception): pass

class SEND:

    def __init__( self, sock, timeout ):
        self.fileno = sock.fileno()
        self.expire = time.time() + timeout

    def __str__( self ):
        return 'SEND(%i,%s)' % ( self.fileno, time.strftime( '%H:%M:%S', time.localtime( self.expire ) ) )


class RECV:

    def __init__( self, sock, timeout ):
        self.fileno = sock.fileno()
        self.expire = time.time() + timeout

    def __str__( self ):
        return 'RECV(%i,%s)' % ( self.fileno, time.strftime( '%H:%M:%S', time.localtime( self.expire ) ) )


class WAIT:

    def __init__( self, timeout = None ):
        self.expire = timeout and time.time() + timeout or None

    def __str__( self ):
        return 'WAIT(%s)' % ( self.expire and time.strftime( '%H:%M:%S', time.localtime( self.expire ) ) )


class Fiber:

    def __init__( self, generator ):
        self.__generator = generator
        self.state = WAIT()

    def step( self, throw=None ):
        self.state = None
        try:
            if throw:
                assert hasattr( self.__generator, 'throw' ), throw
                self.__generator.throw( AssertionError, throw )
            state = self.__generator.next()
            assert isinstance( state, (SEND, RECV, WAIT) ), 'invalid waiting state %r' % state
            self.state = state
        except Restart:
            raise 
        except KeyboardInterrupt:
            raise
        except StopIteration:
            del self.__generator
            pass
        except AssertionError, msg:
            if not str(msg):
                msg = traceback.format_exc()
            log('Assertion failure: %s'% msg)
        except:
            traceback.print_exc()

    def __repr__( self ):
        return '%i: %s' % ( self.__generator.gi_frame.f_lineno, self.state )


class GatherFiber( Fiber ):

    def __init__( self, generator ):
        Fiber.__init__( self, generator )
        self.__chunks = [ '[ 0.00 ] %s\n' % time.ctime() ]
        self.__start = time.time()
        self.__newline = True

    def step( self, throw=None ):
        stdout = sys.stdout
        stderr = sys.stderr
        try:
            sys.stdout = sys.stderr = self
            Fiber.step( self, throw )
        finally:
            sys.stdout = stdout
            sys.stderr = stderr

    def write( self, string ):
        if self.__newline:
            self.__chunks.append( '%6.2f   ' % ( time.time() - self.__start ) )
        self.__chunks.append( string )
        self.__newline = string.endswith( '\n' )

    def __del__( self ):
        sys.stdout.writelines( self.__chunks )
        if not self.__newline:
            sys.stdout.write( '\n' )


class DebugFiber( Fiber ):

    id = 0

    def __init__( self, generator ):
        Fiber.__init__( self, generator )
        self.__id = DebugFiber.id
        sys.stdout.write( '[ %04X ] %s\n' % ( self.__id, time.ctime() ) )
        self.__newline = True
        self.__stdout = sys.stdout
        DebugFiber.id = ( self.id + 1 ) % 65535

    def step( self, throw=None ):
        stdout = sys.stdout
        stderr = sys.stderr
        try:
            sys.stdout = sys.stderr = self
            Fiber.step( self, throw )
            log('Waiting at %s'% self, Params.LOG_DEBUG)
        finally:
            sys.stdout = stdout
            sys.stderr = stderr

    def write( self, string ):
        if self.__newline:
            self.__stdout.write( '  %04X   ' % self.__id )
        self.__stdout.write( string )
        self.__stdout.flush()
        self.__newline = string.endswith( '\n' )


def fork( output, pid_file ):

    try:
        log = open( output, 'w' )
        nul = open( '/dev/null', 'r' )
        pid = os.fork()
    except IOError, e:
        print 'error: failed to open', e.filename
        sys.exit( 1 )
    except OSError, e:
        print 'error: failed to fork process:', e.strerror
        sys.exit( 1 )
    except Exception, e:
        print 'error:', e
        sys.exit( 1 )

    if pid:
        cpid, status = os.wait()
        #print "PID, Status: ", cpid, status
        sys.exit( status >> 8 )

    try: 
        os.chdir( os.sep )
        os.setsid() 
        os.umask( 0 )
        pid = os.fork()
    except Exception, e: 
        print 'error:', e
        sys.exit( 1 )

    if pid:
        open(pid_file, 'wb').write(str(pid))
        print 'Forked process, htcache now at PID', pid
        sys.exit( 0 )

    os.dup2( log.fileno(), sys.stdout.fileno() )
    os.dup2( log.fileno(), sys.stderr.fileno() )
    os.dup2( nul.fileno(), sys.stdin.fileno()  )


def spawn( generator, hostname, port, debug, daemon_log, pid_file ):

    """
    generator
        A generator (callable that yields state changes), 
    port
        Integer.
    debug
        Boolean to indicated wether to use regular GatherFiber or
        DebugFiber.
    log
        Callable.
    pid_file
        Filename.
    """

    import Runtime

    # set up listening socket
    listener = socket.socket( 
                socket.AF_INET, socket.SOCK_STREAM )
    listener.setblocking( 0 )
    listener.setsockopt( 
            socket.SOL_SOCKET, 
            socket.SO_REUSEADDR, 
            listener.getsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR ) | 1 )
    try:
        listener.bind( 
                ( hostname, port ) )
    except:
        log("unable to bind to %s:%i" %(hostname, port), Params.LOG_ERR)
        raise
    listener.listen( 5 )

    # fork and exit for deamon mode
    if daemon_log:
        fork( daemon_log, pid_file )

    # stay attached to console
    if debug:
        myFiber = DebugFiber
    else:
        myFiber = GatherFiber

    log('[ INIT ] %s started at %s:%i' % (generator.__name__, hostname, port ),
            Params.LOG_NOTE)

    try:

        fibers = []

        while True:

            tryrecv = { listener.fileno(): None }
            trysend = {}
            expire = None
            now = time.time()

            i = len( fibers )
            log('[ STEP ] at %s, %s fibers'% (time.ctime(), len(fibers)),
                    Params.LOG_DEBUG)
            while i:
                i -= 1
                state = fibers[ i ].state

                if state and now > state.expire:
                    if isinstance( state, WAIT ):
                        fibers[ i ].step()
                    else:
                        fibers[ i ].step( throw='connection timed out' )
                    state = fibers[ i ].state

                if not state:
                    del fibers[ i ]
                    continue

                if isinstance( state, RECV ):
                    tryrecv[ state.fileno ] = fibers[ i ]
                elif isinstance( state, SEND ):
                    trysend[ state.fileno ] = fibers[ i ]
                elif state.expire is None:
                    continue

                if state.expire < expire or expire is None:
                    expire = state.expire

            if expire is None:
                log('[ IDLE ] at %s, %s fibers'% (time.ctime(), len(fibers)))
                if len(fibers) == 0:
                    assert len(Runtime.DOWNLOADS) == 0
                sys.stdout.flush()
                canrecv, cansend, dummy = select.select( tryrecv, trysend, [] )
                log('[ BUSY ] at %s, %s fibers'% (time.ctime(), len(fibers)))
                sys.stdout.flush()
            else:
                canrecv, cansend, dummy = select.select( tryrecv, trysend, [], max( expire - now, 0 ) )

            #print '[ IO ] Data on', len(canrecv), "inputs,", len(cansend), "outputs"

            for fileno in canrecv:
                #print '[ IO ] Receiving from', tryrecv[fileno]
                if fileno is listener.fileno():
                    fibers.append( myFiber( generator( *listener.accept() ) ) )
                else:
                    tryrecv[ fileno ].step()
            for fileno in cansend:
                #print '[ IO ] Sending to', trysend[fileno]
                trysend[ fileno ].step()

    except KeyboardInterrupt, e:
        log('[ DONE ] %s closing normally'% (generator.__name__), Params.LOG_NOTE)
        sys.exit( 0 )

    except Restart:
        log('[ RESTART ] %s will now respawn' % generator.__name__, Params.LOG_NOTE)
        i = len( fibers )
        while i:
            i -= 1
            #state = fibers[ i ].state
        # close before sending response 
        listener.close()
        raise

    except Exception, e:
        log('[ CRITICAL ] %s crashed: %s' % (generator.__name__, e), Params.LOG_CRIT)
        traceback.print_exc( file=sys.stdout )
        sys.exit( 1 )

