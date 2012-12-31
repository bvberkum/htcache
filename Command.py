"""
"""
import optparse
import os
import socket
import sys
import traceback
from pprint import pformat

import Params
import Runtime
import Resource
import Rules
from util import json_write, log


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


## optparse option attributes

def _cmd(**ext):
    d = dict(
        action="callback", 
        callback=opt_command_flag,
        dest="commands",
        default=[]
    )
    d.update(ext)
    return d

def _dirpath(default):
    return {
            'type': str,
            'metavar': "DIR",
            'default': default,
            'action': "callback",
            'callback': opt_dirpath
        }

def _rulefile(name):
    return {
            'type': str,
            'metavar': "FILE",
            'dest': "%s_file" % name,
            'default': getattr(Params, ("%s_FILE" % name).upper())
        }
             


class CLIParams:

    specification = (
        ( "Proxy", "These options set parameters for the proxy service behaviour. ", (
            (('-a', '--address', '--hostname'),
                # TODO: allow port in address
                "listen on this port for incoming connections, default: %(default)i", dict(
                    metavar="HOST",
                    default=Params.HOSTNAME,
                    dest="hostname",
                    type=str,
            )),
            (('-p', '--port'),
                "listen on this port for incoming connections, default: %(default)i", dict(
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
                    type=int,
                    metavar="RATE",
            )),
            (("-t", "--timeout"),
                "break connection after so many seconds of inactivity,"
                " default %(default)i", dict(
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
#        ( "Query.", (
#            ((None, "--media-image"), "", {}),
#        )),
        ( "Cache", "Parameters that define non-user visible backend behaviour. ", (
            (('--daemon',),
                "daemonize process and print PID, route output to LOG", dict(
                    metavar="LOG",
                    dest="log"
            )),
            (('--pid-file',),
                "set the run file where to write the PID, default is '%(default)s'", dict(
                    metavar="FILE",
                    default=Params.PID_FILE
            )),
            (("-r", "--root"),
                "set cache root directory, default current: %(default)s", 
                _dirpath(Params.ROOT)
            ),
            (("-d", "--data",), "XXX: Change location of var datafiles. Note: cannot change "
                " location of built-in files, only of storages.", dict(
                    type=str,
                    metavar="SQL"
                )
            ),
            (("--data-dir",), "XXX: Change location of var datafiles. Note: cannot change "
                " location of built-in files, only of storages.", 
                _dirpath(Params.DATA_DIR)
            ),
            (("--static-dir",), "XXX: Change location of static datafiles.", 
                _dirpath(Params.DATA_DIR)
            ),
            (("-c", "--cache"),
                "use module for caching, default %(CACHE)s.", dict(
                    metavar="TYPE",
                    default=Params.CACHE,
            )),
            (("-b", "--backend",), "XXX:initialize metadata backend from reference", dict(
                    metavar="REF"
            )),
            (("--nodir",), "", dict(
                action="store_true"
            )),
            (("--partial-suffix",), "", dict(
                dest="partial",
                default=Params.PARTIAL
            )),
#
#    if _arg in ( '-H', '--hash' ):
#        try:
#            ROOT = os.path.realpath( _args.pop(0) ) + os.sep
#            assert os.path.isdir( ROOT )
#        except StopIteration:
#            sys.exit( 'Error: %s requires a directory argument' % _arg )
#        except:
#            sys.exit( 'Error: invalid sha1sum directory %s' % ROOT )
        )),
        ( "Rules", "Configure external files for URL filtering and rewriting. ", (
            (("--drop",),
                "filter requests for URI's based on regex patterns"
                " read line for line from file, default %(default)s", 
                    _rulefile("drop")
            ),
            (("--nocache",),
                "TODO: bypass caching for requests based on URL regex pattern", 
                    _rulefile("nocache")
            ),
            (("--rewrite",),
                "XXX: content rewrite any webresource by selecting on URL or ...??", 
                    _rulefile("rewrite")
            ),
            (("--join",),
                "Rewrites the internal location for requests based on URL RegEx."
                " This can join distinct downloads to a single file, which"
                " may be a problem if its contents has any differences. XXX: read"
                " elsewhere on downloading joining. ",
                    _rulefile("join")
            ),
            (("--join-rule",),
                "XXX: append manual rule", dict()
            ),
            (("--check-join-rules",),
                "XXX: validate and run tests", 
                _cmd()
            ),
            (("--run-join-rules",),
                "XXX: re-run", 
                _cmd()
            ),
        )),
        ( "Misc.", "These affect both the proxy and commands. ", (
            (("-v", "--verbose"),
                "increase output, XXX: use twice to show http headers", dict(
                    action="count"
            )),
            (("--log-level",),
                "set output level explicitly", dict(
                    metavar="[0-9]",
                    type=int,
                    dest="verbose",
                    default=Params.VERBOSE,
                    action="callback",
                    callback=opt_posnum
            )),
            (("-q", "--quiet"),
                "XXX: turn of output printing?", dict(
                    action="store_true",
                    default=Params.QUIET
            )),
            (('--debug',),
                "Switch from gather to debug fiber handler.", dict(
                    action="store_true",
                    default=Params.DEBUG
            ))
        )),
        ( "Query", 
                "", (
            (("--info",),
                "TODO: ", _cmd()
            ),
            (("--list-locations",),
                "Print paths of descriptor locations. ", 
                _cmd()
            ),
            (("--list-resources",),
                "Print URLs of cached resources. ", 
                _cmd()
            ),
            (("--print-resources",),
                "Print all fields for each record; tab separated, one per line.", 
                _cmd()
            ),
            (("--find-records", ),
                "XXX: Query for one or more records by regular expression.", 
                _cmd(metavar="KEY[.KEY]:PATTERN", type=str)
            ),
            (("--print-record", ),
                "",
                _cmd(metavar="URL", type=str)
            ),
        )),
        ( "Maintenance", 
"""See the documentation in ReadMe regarding configuration of the proxy. The
options in this group performan maintenance tasks, and the last following group
gives access to the stored data. """, (
            (("--check-cache",),
                "", _cmd()
            ),
            (("--check-files",),
                "", _cmd()
            ),
# XXX:
#            (("--check-refs",),
#                "TODO: iterate cache references", _cmd()
#            ),
            (("--prune-gone",),
                "TODO: Remove resources no longer online.", _cmd()
            ),
            (("--prune-stale",),
                "Delete outdated cached resources, ie. those that are "
                "expired. Also drops records for missing files. ", _cmd()
            ),
            (("--link-dupes",),
                "TODO: Symlink duplicate content, check by size and hash."
                " Requires up to date hash index.", _cmd()
            ),
#     TODO --print-mode line|tree
#     TODO --print-url
#     TODO --print-path
#                     List either URLs or PATHs only, omit record data.
#     TODO --print-documents
#     TODO --print-videos
#     TODO --print-audio
#     TODO --print-images
#                     Search through predefined list of content-types.
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

        varnames = [ x for x in dir(options) 
                if not callable(getattr(options, x))
                and x[0] != '_' ]
        for n in varnames:
            setattr(Runtime, n.upper(), getattr(options, n))

        Runtime.options, Runtime.arguments = \
                options, arguments

        return prsr, options, arguments


## Generic command line functions

def print_info(return_data=False):

    """
    """

    backend = Resource.get_backend(True)

    Rules.load()

    data = {
        "htcache": {
            "runtime": {
                "online": Runtime.ONLINE,
                "debug": Runtime.DEBUG,
                "static": Runtime.STATIC,
                "pid": open(Runtime.PID_FILE).read().strip(),
                "log-level": Runtime.VERBOSE,
            },
            "config": {
                "proxy": {
                    "hostname": Runtime.HOSTNAME,
                    "port": Runtime.PORT,
                    "socket-family": Runtime.FAMILY,
                    "timeout": Runtime.TIMEOUT,
                },
                "process": {
                    "pid-file": Runtime.PID_FILE,
                    "deamon": Runtime.LOG,
                },
                "backend": {
                    "cache-type": Runtime.CACHE,
                    "root": Runtime.ROOT,
                    "data": Runtime.DATA_DIR,
                },
                "rules": {
                    "join-file": Runtime.JOIN_FILE,
                    "drop-file": Runtime.DROP_FILE,
                    "nocache-file": Runtime.NOCACHE_FILE,
                    "rewrite-file": Runtime.REWRITE_FILE,
                }
            },
            "statistics": {
                "data": {
                    "records": {
                        "resources": len(backend.resources), 
                        "descriptors": len(backend.descriptors), 
                    },
                    "mappings": {
                        "cachemap": len(backend.cachemap), 
                        "resourcemap": len(backend.resourcemap), 
                    }
                },
                "rules": {
                        "drop": len(Rules.Drop.rules),
                       "join": len(Rules.Join.rules),
                        "nocache": len(Rules.Join.rules),
                        "rewrite": len(Rules.Rewrite.rules),
                    }
                }
            }
        }
        
    if return_data:
        return data

    print pformat(data)


### Descriptor/Cache Query static entry

from fnmatch import fnmatch


# XXX:
def path_ignore(path):
    for p in ('*.git*','*.sw[pon]','*.py[c]','*Makefile', '*.py', '*.mk'):
        if fnmatch(path, p):
            return True

def check_joinlist():
    """
    Run joinlist rules over cache references.

    Useful during development since
    """
    Rules.Join.parse()
    Rules.Join.validate()


cmdfunc = {

# Query
        'info': print_info,
        'list-locations': Resource.list_locations,
        'list-resources': Resource.list_urls,
        'find-records': Resource.find_records,
        'print-record': Resource.print_record,

# Rules
        'run-join-rules': Rules.Join.run,
        'check-join-rules': check_joinlist,

# XXX: Maintenance
#        'check-refs': 
#        'prune-gone': 
#        'prune-stale': 
#        'link-dupes': 
#        'validate-cache': Resource.validate_cache,
        'check-cache': Resource.check_cache,
        'check-files': Resource.check_files,
#        'check-refs': Resource.check_files,
}

exceptions = []

def run(cmds={}):
    global exceptions
    
    items = Runtime.options.commands;

    for cmdid, cmdarg in items:

        try:

            cmdfunc[cmdid](cmdarg)

        except Exception, e:
            log("Error: %s" % (e), Params.LOG_ERR)
            etype, value, tb = sys.exc_info()
            exceptions.append((etype, value, tb))

    if items:
        return True

