import sys
import os

import Runtime
import Params


EMERG, \
ALERT, \
CRIT, \
ERR, \
WARN, \
NOTE, \
INFO, \
DEBUG = range(8, 0, -1)


def name(level):
	return [ 'emergency',
		'alert',
		'crit',
		'err',
		'warn',
		'note',
		'info',
		'debug'][7-level]

class Log(object):

	"""
	Goal: Custom logger with no non-standard dependencies.
	"""

	def __init__(self):
		super(Log, self).__init__()
		self.output = None
		self.threshold = None

	def config(self, threshold, location):
		output = None
		if location in ('stderr', 'stdout'):
			output = getattr(sys, location)#.fileno()
		elif not location.startswith(os.sep) and './' not in location and '..' not in location:
			location = os.path.join(Params.LOG_DIR, location)
		if not output:
			try:
				output = open(location, 'w+')
			except Exception, e:
				print "Failed opening location for log ", location
				raise e
		self.output = output
		self.threshold = threshold

#	def __nonzero__(self):
#		"""
#		Determine wether to emit based on call-time environment.
#		"""
#		return \
#				not Runtime.QUIET \
#			and \
#				Runtime.ERROR_LEVEL >= self.level \
#			or ( 
#					( self.facility in Runtime.LOG_FACILITIES ) \
#				and \
#					( Runtime.VERBOSE >= self.level )
#			)

	def emit_check(self, level):
		v = not Runtime.QUIET and level >= self.threshold
		return v

	def emit(self, msg, *args):
		if args:
			print >>self.output, msg % args
		else:
			print >>self.output, msg

	def __getattr__(self, name):
		def level_call(msg, *args):
			if self.emit_check(({
						'emerg': 7,
						'alert': 6,
						'crit': 5,
						'err': 4,
						'warn': 3,
						'note': 2,
						'info': 1,
						'debug': 0,
					})[name]):
				self.emit(msg, *args)
		return level_call

class ModuleLog(Log):
	pass

class ErrorLog(Log):
	pass

class ClientTreeLog(Log):
	pass


LOG_CLASSES = {
	'main': ModuleLog,
	'stderr': ErrorLog,
	'cient-tree': ClientTreeLog
}

def get_log(name):#module=None, level=Params.NOTE, facility=None):
	"""
	Return logger instance for 
	"""
	if name not in Runtime.loggers:
		log_class = LOG_CLASSES[name]
		Runtime.loggers[name] = log_class()
	return Runtime.loggers[name]

def log(args, t=NOTE, f=None):
	return log_(args, t, f)

def log_(args, threshold=NOTE, facility=None):
	"""
	Not much of a log..
	Output if VERBOSE >= threshold
	Use (r)syslog integer levels.
	"""
	if not facility: 
		# set facility to component
		trace = [ 
				( os.path.basename(q), x, y, z )
				for q,x,y,z 
				in traceback.extract_stack() 
			]
		trace.pop()
		if trace:
			if trace[-1][0] == 'util.py':
				trace.pop()
			facility = trace[-1][0].replace('.py', '').lower()
		else:
			facility = 'htcache'
	key = "%s.%i" % (facility, threshold)
	return get_log(threshold, facility)(*args)

