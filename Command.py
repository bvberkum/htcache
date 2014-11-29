"""
"""
import optparse
import os
import socket
import sys
import traceback

import Params
import Runtime
import log


log = log.get_log('main')


## optparse callbacks

def opt_command_flag(option, opt_str, value, parser):
	commands = getattr(parser.values, option.dest)
	commands.append( ( opt_str.strip('-'), value ) )
	setattr(parser.values, option.dest, commands)

def opt_dirpath(option, opt_str, value, parser):
	value = str(value)
	if not os.path.isdir(value):
		raise optparse.OptionValueError(
				"%s argument does not exists or is not a directory: %r" % ( opt_str, value ))
	if value[-1] != os.sep:
		value += os.sep
	setattr(parser.values, option.dest, value)

def opt_posnum(option, opt_str, value, parser):
	try:
		value = int(value)
		assert value > 0
	except:
		raise optparse.OptionValueError("%s requires a positive numerical argument" % opt_str)
	setattr(parser.values, option.dest, value)

def opt_loglevel(option, opt_str, value, parser):
	try:
		value = int(value)
		assert -1 < value < 8
	except:
		raise optparse.OptionValueError("%s requires a numerical argument in the range 0, 7" % opt_str)
	setattr(parser.values, option.dest, value)

def opt_datadir(option, opt_str, value, parser):
	if hasattr(parser.values, 'DATA') and getattr(parser.values.DATA) != None:
		raise optparse.OptionValueError(
				"Cannot set data-dir after database location has been set with --data. ")
	value = str(value)
	if value[0] != os.sep:
		value = os.path.abspath(value)
	if not os.path.isdir(value):
		raise optparse.OptionValueError(
				"%s argument does not exists or is not a directory: %r" % ( opt_str, value ))
	if value[-1] != os.sep:
		value += os.sep

	dbref = "sqlite:///%s/resources.sqlite" % value
	setattr(parser.values, option.dest, value)
	setattr(parser.values, "data", dbref)
#	parser.defaults['data'] = dbref

def opt_log_args(option, opt_str, value, parser):
	args = value.split(',')
	setattr(parser.values, option.dest, args)
	print dir(option)
	print repr(opt_str)
	print repr(args)
	print dir(parser)
	print parser.values

## optparse option attributes

def dict_update(d, **ext):
	d = dict(d)
	d.update(ext)
	return d

_cmd = dict(
		action="callback", 
		callback=opt_command_flag,
		dest="commands",
		default=[]
	)

_dirpath = dict(
		type=str,
		metavar="DIR",
		action="callback",
		callback=opt_dirpath
	)

logger_args = dict(
		type=str, default=None,
		action="callback", callback=opt_log_args
	)

def _rulefile(name):
	return {
			'type': str,
			'metavar': "FILE",
			'dest': "%s_file" % name,
			'default': getattr(Params, ("%s_FILE" % name).upper())
		}


class CLIRuntime:

	specification = (
		( "Proxy", "These options set parameters for the proxy service behaviour. ", (
			(('-a', '--address', '--hostname'),
# TODO: allow port in address
				"listen on this port for incoming connections, default: %default", dict(
					metavar="HOST",
					default=Params.HOSTNAME,
					dest="hostname",
					type=str,
			)),
			(('-p', '--port'),
				"listen on this port for incoming connections, default: %default", dict(
					metavar="PORT",
					default=Params.PORT,
					type=int,
					action="callback",
					callback=opt_posnum,
			)),
			(('--static',),
				"static mode; serve only from cache, do not go online. This"
				" ignores --offline setting.", dict(
					action="store_true",
					default=Params.STATIC
			)),
			(('--flat',),
				"flat cachedir mode; ", dict(
					action="store_true",
					default=Params.FLAT
			)),
			(('--maxchunk',),
				"LAN packet size? ", dict(
					type=int,
					default=Params.MAXCHUNK
			)),
# XXX: write macro to fix this:
			(('--online',),
				"online mode; default. Ignored by --static. ", dict(
					dest="online",
					action="store_true",
					default=Params.ONLINE
			)),
			(('--offline',),
				"offline mode; never connect to server", dict(
					dest="online",
					action="store_false"
			)),
#/XXX
			(('--limit',),
				"TODO: limit download rate at a fixed K/s", dict(
					type=float,
					default=Params.LIMIT,
					metavar="RATE",
			)),
			(("-t", "--timeout"),
				"break connection after so many seconds of inactivity,"
				" default %default", dict(
					metavar="SEC",
					type=int,
					default=Params.TIMEOUT,
					action="callback",
					callback=opt_posnum,
			)),
			(("-6", "--ipv6"),
				"XXX: try ipv6 addresses if available", dict(
					dest="family",
					action="store_const",
					const=socket.AF_UNSPEC,
					default=Params.FAMILY
			)),
		)),
		( "Cache", "Parameters that define non-user visible backend behaviour. ", (
			(('--daemon',),
				"daemonize process and print PID, route output to LOG", dict(
					type=str,
					default=Params.LOG,
					metavar="LOG",
					dest="log"
			)),
#			(('--debug-tag',),
#				"filter out logs and print to separate stream, ", dict(
#					metavar="TAG",
#					dest="log"
#			)),
#			(('--debug-log',),
#				"set the location of a debug log", dict(
#					metavar="TAG;LOG",
#					dest="log"
#			)),
			(('--pid-file',),
				"set the run file where to write the PID, default is '%default'", dict(
					metavar="FILE",
					default=Params.PID_FILE
			)),
			(("-r", "--root"),
				"set cache root directory, defaults to execution directory: %default. ", 
				dict_update(_dirpath, default=Params.ROOT)
			),
#			(("-c", "--cache"),
#				"Module for cache backend, default %default.", dict(
#					metavar="TYPE",
#					default=Params.CACHE,
#			)),
			(("--nodir",), "", dict(
				action="store_true"
			)),
			(("--partial-suffix",), "", dict(
				dest="partial",
				default=Params.PARTIAL
			)),
		)),
		( "Misc.", "These affect both the proxy and commands. ", (
			(("-v", "--verbose"),
				"increase output, XXX: use twice to show http headers", dict(
					action="count",
					default=Params.VERBOSE
			)),
#			(("--log-level",),
#				"set main log output level", dict(
#					metavar="[0-7]",
#					type=int,
#					# dest: error_level
#					default=Params.ERROR_LEVEL,
#					action="callback",
#					callback=opt_loglevel
#			)),
#			(("--error-level",),
#				"set output level to override log-level", dict(
#					metavar="[0-7]",
#					type=int,
#					# dest: error_level
#					default=Params.ERROR_LEVEL,
#					action="callback",
#					callback=opt_loglevel
#			)),
			(("--log-level",),
				"set output level for selected facilities", dict(
					metavar="[0-7]",
					type=int,
					# fixme: rename verbose to log_level some convenient time
					#dest="verbose",
					default=Params.LOG_LEVEL,
					action="callback",
					callback=opt_loglevel
			)),
#			(("--log-main-args",), "", dict_update(logger_args, 
#				metavar="[level,location]",
#				default='0,stdout')),
#			(("--log-error-args",), "", dict_update(logger_args, 
#				metavar="[level,location]",
#				default='0,stderr')),
#			(("--log-module-args",), "", dict_update(logger_args, 
#				metavar="[level,location]",
#				default=Params.LOG_MODULE_ARGS)),
			(("-q", "--quiet"),
				"XXX: turn of output printing?", dict(
					action="store_true",
					default=Params.QUIET
			)),
			(('--debug',),
				"Enable Switch from gather to debug fiber handler.", dict(
					action="store_true",
					default=Params.DEBUG
			)),
		)),
		( "Rules", 
				"", (
			(('--scrap',), "", dict(
					metavar="FILE",
					default=Params.SCRAP
			)),
		)),
		( "Query", 
				"", (
			(("--info",),
				"TODO: ", 
				dict_update(_cmd)
			),
			(("--list-locations",),
				"Print paths of descriptor locations. ", 
				dict_update(_cmd)
			),
			(("--list-resources",),
				"Print URLs of cached resources. ", 
				dict_update(_cmd)
			),
			(("--print-resources",),
				"Print all fields for each record; tab separated, one per line.", 
				dict_update(_cmd)
			),
			(("--find-records", ),
				"XXX: Query for one or more records by regular expression.", 
				dict_update(_cmd, metavar="KEY[.KEY]:PATTERN", type=str)
			),
			(("--print-records", ),
				"",
				dict_update(_cmd)
			),
			(("--print-record", ),
				"",
				dict_update(_cmd, metavar="URL", type=str)
			),
			(("--print-location", ),
				"",
				dict_update(_cmd, metavar="URL", type=str)
			),
		)),
		( "Maintenance", 
"""See the documentation in ReadMe regarding configuration of the proxy. The
options in this group performan maintenance tasks, and the last following group
gives access to the stored data. """, (
			(("--check-cache",),
				"", dict_update(_cmd)
			),
			(("--check-files",),
				"", dict_update(_cmd)
			),
# XXX:
#			(("--check-refs",),
#				"TODO: iterate cache references", dict_update(_cmd)
#			),
			(("--prune-gone",),
				"TODO: Remove resources no longer online.", dict_update(_cmd)
			),
			(("--prune-stale",),
				"Delete outdated cached resources, ie. those that are "
				"expired. Also drops records for missing files. ", dict_update(_cmd)
			),
			(("--link-dupes",),
				"TODO: Symlink duplicate content, check by size and hash."
				" Requires up to date hash index.", dict_update(_cmd)
			),
#	 TODO --print-mode line|tree
#	 TODO --print-url
#	 TODO --print-path
#					 List either URLs or PATHs only, omit record data.
#	 TODO --print-documents
#	 TODO --print-videos
#	 TODO --print-audio
#	 TODO --print-images
#					 Search through predefined list of content-types.
		)),
	)

	@classmethod
	def parse(klass, argv=[]):
		if not argv:
			argv = sys.argv[1:]

		dests = []

		prsr = optparse.OptionParser()
		for grptitle, grpdescr, opts in klass.specification:
			subprsr = optparse.OptionGroup(prsr, grptitle, grpdescr)
			for flags, helptxt, attr in opts:
				attr['help'] = helptxt
				try:
					subprsr.add_option(*flags, **attr)
				except Exception:
					traceback.print_exc()
					raise Exception("Error in option metadata: %r" % [
						flags, attr] )
			prsr.add_option_group(subprsr)

		(options, arguments) = prsr.parse_args(argv)
#
#		if options.log_facilities == []:
#			options.log_facilities = [ 'htcache' ]

		varnames = [ x for x in dir(options) 
				if not callable(getattr(options, x))
				and x[0] != '_' ]
		for n in varnames:
			setattr(Runtime, n.upper(), getattr(options, n))

		Runtime.options, Runtime.arguments = \
				options, arguments

		return prsr, options, arguments


def run(cmds={}):
	"see dev branch"
