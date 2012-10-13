""" """
import os, re, anydbm


try:
    # Py >= 2.4
    assert set
except AssertionError:
    from sets import Set as set

import Params, Cache
#from script_mpe import res
#from script_mpe.res import PersistedMetaObject


class DescriptorStorage(object):

    """
    Base class.
    """

    shelve = None
    "Shelved descriptor objects"
    cachemap = None
    "Map of uriref to cache locations (forward)"
    resourcemap = None
    "Map of cache location to uriref (reverse)"

    def __init__(self, path):
        self.objdb = join(path, 'resources.db')
        self.cachemapdb = join(path, 'cache_map.db')
        self.resourcemapdb = join(path, 'resource_map.db')

        self.shelve = dbshelve.open(objdb)

        self.cachemap = bsddb.hashopen(cachemapdb)
        self.resourcemap = bsddb.hashopen(resourcemapdb)
        #chksmdb = join(path, '.cllct/sha1sum.db')
        #self.sha1sum = dbshelve.open(chksmdb)

    def put(self, uriref, metalink):
        """
        Store or update the descriptor.
        """
        self.shelve[uriref]
        if uriref in self.cachemap:
            self.cache[uriref]

        pass

    def map_path(self, path, uriref):
        pass

    def set(self, uriref, descriptor):
        pass

    def __setitem__(self, path, value):
        self.shelve

#class HTTPEntityHeaders(PersistedMetaObject):
#    pass
#
#class Metalink(PersistedMetaObject):
#    pass

            # TODO: srcrefs, mediatype, charset, language, 
            #if self.has_descriptor():
            #    urirefs, args = self.get_descriptor()
            #else:
            #    urirefs = []
            #if self.requri not in urirefs:
            #    urirefs.append(self.requri)
            #self.descriptors[self.cache.path] = urirefs, self.__args
            #Params.log(self.descriptors[self.cache.path])
            #Params.log("Updated descriptor: %s, %s" %
            #        self.descriptors[self.cache.path])

#class Descriptor(PersistedMetaObject): pass
    
#            db = dbshelve.open(filename)

def strip_root(path):
    if path.startswith(Params.ROOT):
        path = path[len(Params.ROOT):]
    if path.startswith(os.sep):
        path = path[1:]
    return path


### Descriptor Storage types:

class Descriptor(object):

    mapping = [
        'locations',
        'mediatype',
        'size',
        'etag',
        'last_modified',
        'quality_indicator',
        'encodings',
        'language',
        'features',
        'extension_headers',
    ]
    """
    Item names for each tuple index.
    """

    def __init__(self, data):#, be=None):
        assert isinstance(data, tuple)
        if len(data) > len(self.mapping):
            raise ValueError()
        self.__data = data
        self.storage = None
        #if be != None:
        #    self.bind(be)

    def __getattr__(self, name):
        if name in self.mapping:
            idx = self.mapping.index(name)
            return self[idx]
        else:
            return super(Descriptor, self).__getattr__(self, name)

    @property
    def data(self):
        return self.__data

    def bind(self, location, storage):
        self.cache_location = location
        self.storage = storage
        return self

    def __getitem__(self, idx):
        if idx >= len(self.data):
            raise IndexError()
        #if idx < len(self.data):
        return self.__data[idx]

    def __setitem__(self, idx, value):
        self.__data[idx] = value

    def __contains__(self, value):
        return value in self.__data

    def __iter__(self):
        return iter(self.__data)

    def update(self, values):# *values, **kwds):
        if not isinstance(values, Descriptor):
            assert isinstance(values, tuple), values
        else:
            values = values.data
        _update = ()
        len_values = len(values)
        for idx, name in enumerate(self.mapping):
            if len_values == idx:
                break
            if self[idx] != values[idx]:
                self[idx] = values[idx]
                _update += (idx,)
        return _update

    def commit(self):
        ""
        self.storage[self.cache_location] = self

    def from_headers(class_, args):
        for hn in Protocol.HTTP.Cache_Headers:
            
            pass


class DescriptorStorage(object):

    """
    Item is the local path to a cached resource.
    """

    def __init__(self, *params):
        pass

    def __getitem__(self, path):
        path = strip_root(path)
        if path in self:
            return self.get(path)
        else:
            d = Descriptor((None,) * len(Descriptor.mapping))\
                .bind(path, self)
            return d

    def __setitem__(self, path, values):
        if not isinstance(values, Descriptor):
            assert isinstance(values, tuple)
        else:
            values = values.data
        if path in self:
            self[path].update(values)
        else:
            new_values = self[path]
            new_values.update(values)
            self.set(path, new_values)

    def __contains__(self, path):
        raise AbstractClass()

    def __len__(self):
        raise AbstractClass()

    def __iter__(self):
        raise AbstractClass()

    def get(self, path):
        raise AbstractClass()

    def set(self, path, name, value):
        raise AbstractClass()

    def commit(self):
        raise AbstractClass()

    def close(self):
        raise AbstractClass()


class FileStorage(object):
    def __init__(self):
        raise "Not implemented: FileStorage"
    def close(self): pass
    def update(self, hrds): pass


# FIXME: old master
# class AnyDBStorage(DescriptorStorage):
class AnyDBStorage(object):

    def __init__(self, path, mode='rw'):
        if not os.path.exists(path):
            assert 'w' in mode
            try:
                anydbm.open(path, 'n').close()
            except Exception, e:
                raise Exception("Unable to create new resource DB at <%s>: %s" %
                        (path, e))
        try:
            Params.log("Opening %s mode=%s" %(path, mode))
            self.__be = anydbm.open(path, mode)
        except anydbm.error, e:#bsddb.db.DBAccessError, e:
            raise Exception("Unable to access resource DB at <%s>: %s" %
                    (path, e))

    def close(self):
        self.__be.close()

    def keys(self):
        return self.__be.keys()

    def __contains__(self, path):
        path = strip_root(path)
        return self.has_path(path)

    def __iter__(self):
        return iter(self.__be)

    def __setitem__(self, path, value):
        if path in self.__be:
            self.update(path, *value)
        else:
            self.set(path, *value)

    def __getitem__(self, path):
        return self.get(path)

    def __delitem__(self, path):
        del self.__be[path]

    def has(self, path):
        return path in self.__be

    def get(self, path):
        data = self.__be[path]
        value = tuple(Params.json_read(data))
        return Descriptor(value, be=self)
# FIXME: current dev
#        return tuple(Params.json_read(self.__be[path]))

    def set(self, path, srcrefs, headers):
        assert path and srcrefs and headers, \
            (path, srcrefs, headers)
        assert isinstance(path, basestring) and \
            isinstance(srcrefs, list) and \
            isinstance(headers, dict)
        mt = headers.get('Content-Type', None)
        cs = None
        if mt:
            p = mt.find(';')
            if p > -1:
              match = re.search("charset=([^;]+)", mt[p:].lower())
              mt = mt[:p].strip()
              if match:
                  cs = match.group(1).strip()
        ln = headers.get('Content-Language',[])
        if ln: ln = ln.split(',')
        srcref = headers.get('Content-Location', None)
        #if srcref and srcref not in srcrefs:
        #      srcrefs += [srcref]
        features = {}
        metadata = {}
        for hd in ('Content-Type', 'Content-Language', 'Content-MD5',
              'Content-Location', 'Content-Length', 'Content-Encoding',
              'ETag', 'Last-Modified', 'Date', 'Vary', 'TCN',
              'Cache', 'Expires'):
            if hd in headers:
                metadata[hd] = headers[hd]
        self.__be[path] = Params.json_write((srcrefs, mt, cs, ln, metadata, features))
        self.__be.sync()

    def update(self, path, srcrefs, headers):
        descr = self.get(path)
        srcrefs = list(set(srcrefs).union(descr[0]))
        headers.update(descr[4])
        self.set(path, srcrefs, headers)

#    def update_descriptor(self, srcref, mediatype=None, charset=None,
#            languages=[], features={}):
#        assert not srcrefs or (isinstance(srcrefs, list) \
#                and isinstance(srcrefs[0], str)), srcrefs
#        assert not languages or (isinstance(languages, list) \
#                and isinstance(languages[0], str)), languages
#        _descr = self.get_descriptor()
#        if srcrefs:
#              _descr[0] += srcrefs
#        if features:
#              _descr[4].update(features)
#        self.set_descriptor(*_descr)

#    def set_descriptor(self, srcrefs, mediatype, charset, languages,
#            features={}):
#        assert self.cache.path, (self,srcrefs,)
#        if srcrefs and not (isinstance(srcrefs, tuple) \
#                or isinstance(srcrefs, list)):
#            assert isinstance(srcrefs, str)
#            srcrefs = (srcrefs,)
#        assert not srcrefs or (
#                (isinstance(srcrefs, tuple) or isinstance(srcrefs, list)) \
#                and isinstance(srcrefs[0], str)), srcrefs


backend = None

# FIXME: old master global storage
if os.path.isdir(Params.RESOURCES):
#    backend =  FileStorage(Params.RESOURCES)
    Params.descriptor_storage_type = FileStorage

elif Params.RESOURCES.endswith('.db'):
    Params.descriptor_storage_type = AnyDBStorage
#    backend =  FileStorage(Params.RESOURCES)

def get_backend(main=True):
    global backend
    if main:
        if not backend:
            backend = Params.descriptor_storage_type(Params.RESOURCES)
        return backend
    return Params.descriptor_storage_type(Params.RESOURCES, 'r') 

class RelationalStorage(DescriptorStorage):

    def __init__(self, dbref):
        engine = create_engine(dbref)
        self._session = sessionmaker(bind=engine)()

    def get(self, url):
        self._session.query(
                taxus.data.Resource, taxus.data.Locator).join('lctr').filter_by(ref=url).all()


def _is_db(be):
    # file -s resource.db | grep -i berkeley
    return os.path.isdir(os.path.dirname(be)) and be.endswith('.db')

def _is_sql(be):
    # file -s resource.db | grep -i sqlite
    return \
        be.startswith('sqlite:///') or \
        be.startswith('mysql://') or \
        be.endswith('.sqlite')

#Params.BACKENDS.update(dict(
#        # TODO: filestorage not implemented
#        file= (lambda p: os.path.isdir(p), FileStorage),
#        anydb= (_is_db, AnyDBStorage),
#        sql= (_is_sql, RelationalStorage)
#    ))
#
# FIXME : old master
#def init_backend(request, be=Params.BACKEND):
#
#    for name in Params.BACKENDS:
#        if Params.BACKENDS[name][Params.BD_IDX_TEST](be):
#            return Params.BACKENDS[name][Params.BD_IDX_TYPE](be)
#
#    raise Exception("Unable to find backend type of %r" % be)

def get_cache(hostinfo, req_path):

    # Prepare default cache location
    cache_location = '%s:%i/%s' % (hostinfo + (req_path,))
    
    cache_location = cache_location.replace(':80', '')
    # Try Join rules
    #if Params.JOIN:
    #    # FIXME: include hostname:
    #    loc2 = hostinfo[0] +'/'+ envelope[1]
    #    loc3 = joinlist_rewrite(loc2)
    #    if loc2 != loc3:
    #        cache_location = loc3

    # cache_location is a URL path ref including query-part
    # backend will determine real cache location
    cache = Cache.load_backend_type(Params.CACHE)(cache_location)
    Params.log("%s %s" % (Params.CACHE, cache))
    Params.log('Prepped cache, position: %s' % cache.path, 1)
    cache.descriptor_key = cache_location
    return cache


# psuedo-Main: special command line options allow resource DB queries:

def print_info(*paths):
    import sys
    recordcnt = 0
    for path in paths:
        if not path.startswith(os.sep):
            path = Params.ROOT + path
        if path not in backend:
            print >>sys.stderr, "Unknown cache location: %s" % path
        else:
            print path, backend[path]
            recordcnt += 1
    if recordcnt > 1:
        print >>sys.stderr, "Found %i records for %i paths" % (recordcnt,len(paths))
    elif recordcnt == 1:
        print >>sys.stderr, "Found one record"
    else:
        print >>sys.stderr, "No record found"
    backend.close()
    sys.exit(0)

def print_media_list(*media):
    "document, application, image, audio or video (or combination)"
    for m in media:
        # TODO: documents
        if m == 'image':
            for path in backend:
                res = backend[path]
                if 'image' in res[1]:
                    print path
        if m == 'audio':
            for path in backend:
                res = backend[path]
                if 'audio' in res[1]:
                    print path
        if m == 'videos':
            for path in backend:
                res = backend[path]
                if 'video' in res[1]:
                    print path
    import sys
    sys.exit()

def find_info(props):
    import sys
    for path in backend:
        res = backend[path]
        for k in props:
            if k in ('0','srcref'):
                if props[k] in res[0]:
                    print path
            elif k in ('1','mediatype'):
                if props[k] == res[1]:
                    print path
            elif k in ('2','charset'):
                if props[k] == res[2]:
                    print path
            elif k in ('3','language'):
                if props[k] in res[3]:
                    print path
            elif k in ('4','feature'):
                for k2 in props[k]:
                    if k2 not in res[4]:
                        continue
                    if res[4][k2] == props[k][k2]:
                        print path
    backend.close()
    sys.exit(1)

## Maintenance functions
def check_cache(cache, uripathnames, mediatype, d1, d2, meta, features):
    """
    References in descriptor cache must exist as file. 
    This checks existence and the size property,  if complete.

    All rules should be applied.
    """
    if not Params.VERBOSE:
        Params.VERBOSE = 1
    pathname = cache.path
    if cache.partial():
        pathname += '.incomplete'
    if not (cache.partial() or cache.full()):
        Params.log("Missing %s" % pathname)
        return
    if 'Content-Length' not in meta:
        Params.log("Missing content length of %s" % pathname)
        return
    length = int(meta['Content-Length'])
    if cache.full() and os.path.getsize(pathname) != length:
        Params.log("Corrupt file: %s, size should be %s" % (pathname, length))
        return
    #else:
    #    print pathname, meta

    #print pathname, meta
    return True

def validate_cache(pathname, uripathnames, mediatype, d1, d2, meta, features):
    """
    Descriptor properties must match those of file.
    This recalculates the files checksum.
    """
    return True

def check_tree(pathname, uripathnames, mediatype, d1, d2, meta, features):
    return True

def check_joinlist(pathname, uripathnames, mediatype, d1, d2, meta, features):
    """
    Run joinlist rules over cache references.

    Useful during development since 
    """
    return True


#DescriptorStorage(Params.DATA_DIR)

import sys, re

class TerminalController:
    """
    A class that can be used to portably generate formatted output to
    a terminal.  
    
    `TerminalController` defines a set of instance variables whose
    values are initialized to the control sequence necessary to
    perform a given action.  These can be simply included in normal
    output to the terminal:

        >>> term = TerminalController()
        >>> print 'This is '+term.GREEN+'green'+term.NORMAL

    Alternatively, the `render()` method can used, which replaces
    '${action}' with the string required to perform 'action':

        >>> term = TerminalController()
        >>> print term.render('This is ${GREEN}green${NORMAL}')

    If the terminal doesn't support a given action, then the value of
    the corresponding instance variable will be set to ''.  As a
    result, the above code will still work on terminals that do not
    support color, except that their output will not be colored.
    Also, this means that you can test whether the terminal supports a
    given action by simply testing the truth value of the
    corresponding instance variable:

        >>> term = TerminalController()
        >>> if term.CLEAR_SCREEN:
        ...     print 'This terminal supports clearning the screen.'

    Finally, if the width and height of the terminal are known, then
    they will be stored in the `COLS` and `LINES` attributes.
    """
    # Cursor movement:
    BOL = ''             #: Move the cursor to the beginning of the line
    UP = ''              #: Move the cursor up one line
    DOWN = ''            #: Move the cursor down one line
    LEFT = ''            #: Move the cursor left one char
    RIGHT = ''           #: Move the cursor right one char

    # Deletion:
    CLEAR_SCREEN = ''    #: Clear the screen and move to home position
    CLEAR_EOL = ''       #: Clear to the end of the line.
    CLEAR_BOL = ''       #: Clear to the beginning of the line.
    CLEAR_EOS = ''       #: Clear to the end of the screen

    # Output modes:
    BOLD = ''            #: Turn on bold mode
    BLINK = ''           #: Turn on blink mode
    DIM = ''             #: Turn on half-bright mode
    REVERSE = ''         #: Turn on reverse-video mode
    NORMAL = ''          #: Turn off all modes

    # Cursor display:
    HIDE_CURSOR = ''     #: Make the cursor invisible
    SHOW_CURSOR = ''     #: Make the cursor visible

    # Terminal size:
    COLS = None          #: Width of the terminal (None for unknown)
    LINES = None         #: Height of the terminal (None for unknown)

    # Foreground colors:
    BLACK = BLUE = GREEN = CYAN = RED = MAGENTA = YELLOW = WHITE = ''
    
    # Background colors:
    BG_BLACK = BG_BLUE = BG_GREEN = BG_CYAN = ''
    BG_RED = BG_MAGENTA = BG_YELLOW = BG_WHITE = ''
    
    _STRING_CAPABILITIES = """
    BOL=cr UP=cuu1 DOWN=cud1 LEFT=cub1 RIGHT=cuf1
    CLEAR_SCREEN=clear CLEAR_EOL=el CLEAR_BOL=el1 CLEAR_EOS=ed BOLD=bold
    BLINK=blink DIM=dim REVERSE=rev UNDERLINE=smul NORMAL=sgr0
    HIDE_CURSOR=cinvis SHOW_CURSOR=cnorm""".split()
    _COLORS = """BLACK BLUE GREEN CYAN RED MAGENTA YELLOW WHITE""".split()
    _ANSICOLORS = "BLACK RED GREEN YELLOW BLUE MAGENTA CYAN WHITE".split()

    def __init__(self, term_stream=sys.stdout):
        """
        Create a `TerminalController` and initialize its attributes
        with appropriate values for the current terminal.
        `term_stream` is the stream that will be used for terminal
        output; if this stream is not a tty, then the terminal is
        assumed to be a dumb terminal (i.e., have no capabilities).
        """
        # Curses isn't available on all platforms
        try: import curses
        except: return

        # If the stream isn't a tty, then assume it has no capabilities.
        if not term_stream.isatty(): return

        # Check the terminal type.  If we fail, then assume that the
        # terminal has no capabilities.
        try: curses.setupterm()
        except: return

        # Look up numeric capabilities.
        self.COLS = curses.tigetnum('cols')
        self.LINES = curses.tigetnum('lines')
        
        # Look up string capabilities.
        for capability in self._STRING_CAPABILITIES:
            (attrib, cap_name) = capability.split('=')
            setattr(self, attrib, self._tigetstr(cap_name) or '')

        # Colors
        set_fg = self._tigetstr('setf')
        if set_fg:
            for i,color in zip(range(len(self._COLORS)), self._COLORS):
                setattr(self, color, curses.tparm(set_fg, i) or '')
        set_fg_ansi = self._tigetstr('setaf')
        if set_fg_ansi:
            for i,color in zip(range(len(self._ANSICOLORS)), self._ANSICOLORS):
                setattr(self, color, curses.tparm(set_fg_ansi, i) or '')
        set_bg = self._tigetstr('setb')
        if set_bg:
            for i,color in zip(range(len(self._COLORS)), self._COLORS):
                setattr(self, 'BG_'+color, curses.tparm(set_bg, i) or '')
        set_bg_ansi = self._tigetstr('setab')
        if set_bg_ansi:
            for i,color in zip(range(len(self._ANSICOLORS)), self._ANSICOLORS):
                setattr(self, 'BG_'+color, curses.tparm(set_bg_ansi, i) or '')

    def _tigetstr(self, cap_name):
        # String capabilities can include "delays" of the form "$<2>".
        # For any modern terminal, we should be able to just ignore
        # these, so strip them out.
        import curses
        cap = curses.tigetstr(cap_name) or ''
        return re.sub(r'\$<\d+>[/*]?', '', cap)

    def render(self, template):
        """
        Replace each $-substitutions in the given template string with
        the corresponding terminal control string (if it's defined) or
        '' (if it's not).
        """
        return re.sub(r'\$\$|\${\w+}', self._render_sub, template)

    def _render_sub(self, match):
        s = match.group()
        if s == '$$': return s
        else: return getattr(self, s[2:-1])

class ProgressBar:
    """
    A 3-line progress bar, which looks like::
    
                                Header
        20% [===========----------------------------------]
                           progress message

    The progress bar is colored, if the terminal supports color
    output; and adjusts to the width of the terminal.
    """
    BAR = '%3d%% ${GREEN}[${BOLD}%s%s${NORMAL}${GREEN}]${NORMAL}\n'
    BAR = '%3d%% ${BOLD}[${BLUE}%s${NORMAL}%s${NORMAL}]${NORMAL}\n'
    HEADER = '${BOLD}${CYAN}%s${NORMAL}\n\n'
        
    def __init__(self, term, header):
        self.term = term
        if not (self.term.CLEAR_EOL and self.term.UP and self.term.BOL):
            raise ValueError("Terminal isn't capable enough -- you "
                             "should use a simpler progress dispaly.")
        self.width = self.term.COLS or 75
        self.bar = term.render(self.BAR)
        self.header = self.term.render(self.HEADER % header.center(self.width))
        self.cleared = 1 #: true if we haven't drawn the bar yet.
        self.update(0, '')

    def update(self, percent, message):
        if self.cleared:
            sys.stdout.write(self.header)
            self.cleared = 0
        n = int((self.width-10)*percent)
        sys.stdout.write(
            self.term.BOL + self.term.UP + self.term.CLEAR_EOL +
            self.term.BOL + self.term.UP + self.term.CLEAR_EOL +
            (self.bar % (100*percent, '='*n, '-'*(self.width-10-n))) +
            self.term.CLEAR_EOL + message.center(self.width))

    def clear(self):
        if not self.cleared:
            sys.stdout.write(self.term.BOL + self.term.CLEAR_EOL +
                             self.term.UP + self.term.CLEAR_EOL +
                             self.term.UP + self.term.CLEAR_EOL)
            self.cleared = 1


