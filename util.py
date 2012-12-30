from UserDict import UserDict, IterableUserDict

# XXX: Dont use cjson, its buggy, see comments at
# http://pypi.python.org/pypi/python-cjson
# use jsonlib or simplejson
try:
    import simplejson as _json
except:
    import json as _json

json_read = _json.loads
json_write = _json.dumps


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

def log(msg, threshold=5):
    """
    Not much of a log..
    Output if VERBOSE >= threshold
    Use (r)syslog integer levels.
    """
    #assert not threshold == 0
    # see fiber.py which manages stdio
    import Runtime
    if Runtime.VERBOSE >= threshold:
        print msg



