

import sys, os, select, time, socket, traceback

import Params
import Resource
import Rules
import Runtime
import log


mainlog = log.get_log('main')

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
#		except AssertionError, msg:
#			if not str(msg):
#				msg = traceback.format_exc()
#			log('Assertion failure: %s'% msg)
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
			mainlog.debug('Waiting at %s', self)
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

	"""
	Fork process, and make subprocess a session leader (break away from current terminal)
	so it does not receive any signals from here.

	Then fork away from the session leader to prevent any control terminal from
	attaching again. We don't want a controlling terminal for the proxy process. 
	For monitoring and control, we'll use HTTP or a separate process that
	reads from FIFO or file logs.
	"""

	# Make temporary sub process
	try:
		log = open( output, 'w' )
		nul = open( '/dev/null', 'r' )
		pid = os.fork()
	except IOError, e:
		mainlog.crit('[ FORK ] Error: failed to open %s', e.filename)
		sys.exit( 1 )
	except OSError, e:
		mainlog.crit('[ FORK ] Error: failed to fork process: %s', e.strerror)
		sys.exit( 1 )
	except Exception, e:
		mainlog.crit('[ FORK ] Error: %s', e )
		sys.exit( 1 )

	if pid:
		#mainlog.debug(' [ FORK ] Waiting for daemon to start...')
		# Wait for second fork to complete, then exit current process
		temp_pid, status = os.wait()
		mainlog.debug( '[ FORK ] OK, daemon running.')
		sys.exit( status >> 8 )
	else:
		mainlog.note( '[ FORK ] preparing daemon process with log %s ', output )

	try: 
		os.chdir( os.sep )
		os.umask( 0 )
		# set our first fork as session leader
		os.setsid() 
		# now fork to process that will run htcache
		pid2 = os.fork()
	except Exception, e: 
		print 'fork2 error:', e
		sys.exit( 1 )

	if pid2:
		open(pid_file, 'wb').write(str(pid2))
		sys.exit( 0 )
		mainlog.note( '[ FORK ] Daemon running at PID %s ', pid2 )
	else:
		mainlog.debug( '[ FORK ] Continueing daemon ' )

	# xxx; if we do this from the session leader, when/how does this become a controlling terminal?
	os.dup2( log.fileno(), sys.stdout.fileno() )
	os.dup2( log.fileno(), sys.stderr.fileno() )
	os.dup2( nul.fileno(), sys.stdin.fileno() )

	return pid2


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

	if daemon_log:
		# continue as new process in its own session
		pid = fork( daemon_log, pid_file )
		if pid:
			mainlog.debug('[ FIBER ] Forked to PID %s', PID)
			return
		else:
			mainlog.debug('[ FIBER ] Continueing proxy startup')


	# set up listening socket
	listener = socket.socket( 
				socket.AF_INET, socket.SOCK_STREAM )
	listener.setblocking( 0 )
	listener.setsockopt( 
			socket.SOL_SOCKET, 
			socket.SO_REUSEADDR, 
			listener.getsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR ) | 1 )

	try:
		listener.bind( ( hostname, port ) )
		mainlog.debug("[ BIND ] Started serving at %s:%i", hostname, port)
	except:
		mainlog.err("[ ERR ] Unable to bind to %s:%i", hostname, port)
		raise
	listener.listen( 5 )

	if debug:
		myFiber = DebugFiber
	else:
		myFiber = GatherFiber

	mainlog.note('[ INIT ] %s started at %s:%i', generator.__name__, hostname, port )

	Resource.get_backend()
	Rules.load()

	try:

		fibers = []

		while True:

			tryrecv = { listener.fileno(): None }
			trysend = {}
			expire = None
			now = time.time()

			i = len( fibers )
			
			mainlog.debug('[ STEP ] at %s, %s fibers', time.ctime(), len(fibers))

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
				mainlog.note('[ IDLE ] at %s, %s fibers'% (time.ctime(), len(fibers)))
				# XXX
				if len(fibers) == 0:
					import Runtime
					assert len(Runtime.DOWNLOADS) == 0, Runtime.DOWNLOADS
				sys.stdout.flush()
				canrecv, cansend, dummy = select.select( tryrecv, trysend, [] )
				mainlog.note('[ BUSY ] at %s, %s fibers'% (time.ctime(), len(fibers)))
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
		mainlog.note('[ DONE ] %s closing normally', generator.__name__)
		Resource.get_backend().close()
		sys.exit( 0 )

	except Restart:
		mainlog.note('[ RESTART ] %s will now respawn', generator.__name__)
		i = len( fibers )
		while i:
			i -= 1
			#state = fibers[ i ].state
		# close before sending response 
		listener.close()
		Resource.get_backend().close()
		raise

	except Exception, e:
		mainlog.crit('[ CRIT ] %s crashed: %s', generator.__name__, e)
		traceback.print_exc( file=sys.stdout )
		Resource.get_backend().close()
		sys.exit( 1 )

	mainlog.crit('[ END ] %s ', generator)

