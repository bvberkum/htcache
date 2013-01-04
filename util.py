import os
import sys
from UserDict import UserDict, IterableUserDict
import traceback

# XXX: Dont use cjson, its buggy, see comments at
# http://pypi.python.org/pypi/python-cjson
# use jsonlib or simplejson
try:
    import simplejson as _json
except:
    import json as _json

json_read = _json.loads
json_write = _json.dumps

import Params
import Runtime



class LowercaseDict(IterableUserDict):

    """
    A (str, value) map where the key is lowercased on get, set, del and contains.
    """

    def __getitem__(self, name):
        return IterableUserDict.__getitem__(self, name.lower())

    def __setitem__(self, name, value):
        return IterableUserDict.__setitem__(self, name.lower(), value)

    def __delitem__(self, name):
        return IterableUserDict.__delitem__(self, name.lower())

    def __contains__(self, name):
        return IterableUserDict.__contains__(self, name.lower())

    def update(self, obj=None, **kwargs):
        if not (obj or kwargs):
            return
        #elif isinstance(dict, IterableUserDict):
        #    for k in dict.keys():
        #        v = dict[k]
        #        self[k] = v
        if len(kwargs):
            for k, v in kwargs.items():
                self[k] = v
        if not obj:
            return
        if isinstance(obj, type({})) or not hasattr(obj, 'items'):
            for k in obj.keys():
                v = obj[k]
                self[k] = v
        else:
            for k, v in obj.items():
                self[k] = v

class HeaderDict(LowercaseDict):

    """
    Inherits from LowercaseDict but internally keeps a second map with the
    properly capitalized key.
    This will be more usefull for message headers.
    """

    __keys = None
    "Mapping of keys to proper case. "

    def __init__(self, *args):
        self.__keys = {}
        IterableUserDict.__init__(self, *args)

    def __setitem__(self, name, value):
        self.__keys[name.lower()] = name
        return LowercaseDict.__setitem__( self, name, value )

    def __delitem__(self, name):
        del self.__keys[name.lower()]
        LowercaseDict.__delitem__(self, name)

    def keys(self):
        return self.__keys.values()

    def clear(self):
        self.__keys = {}
        LowercaseDict.clear(self)


def cn(obj):
    return obj.__class__.__name__

def print_str(s, l = 79):
    print_line = s.strip()
    hl = (l-7) / 2
    if len(print_line) > l:
        print_line = print_line[:hl] +' [...] '+ print_line[-hl:]
    return print_line


class Log:

    instances = {}

    def __init__(self, level, facility):
        self.level = level
        self.facility = facility

    def __nonzero__(self):
        return \
                not Runtime.QUIET \
            and \
                Runtime.ERROR_LEVEL >= self.level \
            or ( 
                    ( self.facility in Runtime.LOG_FACILITIES ) \
                and \
                    ( Runtime.VERBOSE >= self.level )
            )

    def __call__(self, msg, *args):
        if self:
            if args:
                print msg % args
            else:
                print msg


def get_log(threshold=Params.LOG_NOTE, facility=None):
    """
    Return a "no-op" logger (that evaluates to None but does have the pertinent
    methods). This allows to contain code that should only be run in debug
    modes in conditional scopes. k
    """
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
    if key not in Log.instances:
        Log.instances[key] = Log(threshold, facility)
    return Log.instances[key]


def log(msg, threshold=Params.LOG_NOTE, facility='default'):
    """
    Not much of a log..
    Output if VERBOSE >= threshold
    Use (r)syslog integer levels.
    """
    return get_log(threshold, facility)(msg)


def strstr(s):
    return s.strip('"')

def min_pos(*args):
    "Return smallest of all arguments (but >0)"
    r = sys.maxint
    for a in args:
        if a > -1:
            r = min( a, r )
    return r



