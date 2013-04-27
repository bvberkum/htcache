""" 

Class for descriptor storage.

TODO: filter out unsupported headers, always merge with server headers
 to client.
"""
import anydbm, datetime, os, re, urlparse
from pprint import pformat


try:
    # Py >= 2.4
    assert set
except AssertionError:
    from sets import Set as set

import Params
from error import *

#import uriref
import Params, Cache



class old_DescriptorStorage(object):

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

    def __str__(self):
        return "[Descriptor %s]" % pformat(self.__data)


class old_2_DescriptorStorage(object):

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
        except anydbm.error, e:
            raise Exception("Unable to access resource DB at <%s>: %s" %
                    (path, e))

    def close(self):
        self.__be.close()

    def keys(self):
        return self.__be.keys()

    def __contains__(self, path):
        #path = strip_root(path)
        return self.has(path)

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
        return Descriptor(value)#, be=self)

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


if os.path.isdir(Params.RESOURCES):
    Params.descriptor_storage_type = FileStorage

elif Params.RESOURCES.endswith('.db'):
    Params.descriptor_storage_type = AnyDBStorage

backend = None

def get_backend(main=True):
    global backend
    if main:
        if not backend:
            backend = Params.descriptor_storage_type(Params.RESOURCES)
        return backend
    return Params.descriptor_storage_type(Params.RESOURCES, 'r') 


#class RelationalStorage(DescriptorStorage):
#
#    def __init__(self, dbref):
#        engine = create_engine(dbref)
#        self._session = sessionmaker(bind=engine)()
#
#    def get(self, url):
#        self._session.query(
#                taxus.data.Resource, taxus.data.Locator).join('lctr').filter_by(ref=url).all()


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
    """
    req_path is a URL path ref including query-part,
    the backend will determine real cache location
    """
    # Prepare default cache location
    cache_location = '%s:%i/%s' % (hostinfo + (req_path,))
    cache_location = cache_location.replace(':80', '')
    cache = Cache.load_backend_type(Params.CACHE)(cache_location)
    Params.log("Init cache: %s %s" % (Params.CACHE, cache), 3)
    Params.log('Prepped cache, position: %s' % cache.path, 2)
# XXX: use unrewritten path as descriptor key, need unique descriptor per resource
    cache.descriptor_key = cache_location
    return cache


# psuedo-Main: special command line options allow resource DB queries:

def print_info(*paths):
    import sys
    recordcnt = 0
    backend = get_backend(False)
    for path in paths:
        if not path.startswith(os.sep):
            path = Params.ROOT + path
#        path = path.replace(Params.ROOT, '')
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
    print "End of printinfo"; sys.exit(0)

def print_media_list(*media):
    "document, application, image, audio or video (or combination)"
    backend = get_backend(False)
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
    print "end of media-list"; sys.exit()

def find_info(q):
    import sys
    backend = get_backend(False)
    print 'Searching for', q
    for path in backend:
        res = backend[path]
        urls, mime, qs, n, meta, feats = res
        for u in urls:
            if q in u:
                print path, mime, urls
# XXX:
#        for k in props:
#            if k in ('0','srcref'):
#                if props[k] in res[0]:
#                    print path
#            elif k in ('1','mediatype'):
#                if props[k] == res[1]:
#                    print path
#            elif k in ('2','charset'):
#                if props[k] == res[2]:
#                    print path
#            elif k in ('3','language'):
#                if props[k] in res[3]:
#                    print path
#            elif k in ('4','feature'):
#                for k2 in props[k]:
#                    if k2 not in res[4]:
#                        continue
#                    if res[4][k2] == props[k][k2]:
#                        print path
    backend.close()
    print "End of findinfo"; sys.exit(1)

## Maintenance functions
def check_descriptor(cache, uripathnames, mediatype, d1, d2, meta, features):
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

def check_files():
    if Params.PRUNE:
        descriptors = get_backend()
    else:
        descriptors = get_backend(main=False)
    pcount, rcount = 0, 0
    Params.log("Iterating paths in cache root location. ")
    for root, dirs, files in os.walk(Params.ROOT):

        # Ignore files in root
        if not root[len(Params.ROOT):]:
            continue

#    	rdir = os.path.join(Params.ROOT, root)
        for f in dirs + files:
            f = os.path.join(root, f)
            #if path_ignore(f):
            #    continue
            pcount += 1
            if f not in descriptors:
                if os.path.isfile(f):
                    Params.log("Missing descriptor for %s" % f)
                    if Params.PRUNE:
                        size = os.path.getsize(f)
                        if size < Params.MAX_SIZE_PRUNE:
                            os.unlink(f)
                            Params.log("Removed unknown file %s" % f)
                        else:
                            Params.log("Keeping %sMB" % (size / (1024 ** 2)))#, f))
                elif not (os.path.isdir(f) or os.path.islink(f)):
                    Params.log("Unrecognized path %s" % f)
            elif f in descriptors:
                rcount += 1
                descr = descriptors[f]
                assert isinstance(descr, Descriptor)
                uriref = descr[0][0]
                Params.log("Found resource %s" % uriref, threshold=1)
# XXX: hardcoded paths.. replace once Cache/Resource is properly implemented
                port = 80
                if len(descr[0]) != 1:
                    Params.log("Multiple references %s" % f)
                    continue
                urlparts = urlparse.urlparse(uriref)
                hostname = urlparts.netloc
                pathname = urlparts.path[1:] 
# XXX: cannot reconstruct--, or should always normalize?
                if urlparts.query:
                    #print urlparts
                    pathname += '?'+urlparts.query
                hostinfo = hostname, port
                cache = get_cache(hostinfo, pathname)
                #print 'got cache', cache.getsize(), cache.path
# end
    Params.log("Finished checking %s cache locations, found %s resources" % (
        pcount, rcount))
    descriptors.close()
    sys.exit(0)

def check_cache():
    #term = Resource.TerminalController()
    #print term.render('${YELLOW}Warning:${NORMAL}'), 'paper is crinkled'
    #pb = Resource.ProgressBar(term, 'Iterating descriptors')
    if Params.PRUNE:
        descriptors = get_backend()
    else:
        descriptors = get_backend(main=False)
    refs = descriptors.keys()
    count = len(refs)
    Params.log("Iterating %s descriptors" % count)
    for i, ref in enumerate(refs):
        if Params.VERBOSE > 2:
            print i, ref
        descr = descriptors[ref]
        Params.log("Descriptor data: [%s] %r" %(ref, descr.data,), 2)
        urirefs, mediatype, d1, d2, meta, features = descr
        #progress = float(i)/count
        #pb.update(progress, ref)
# XXX: hardcoded paths.. replace once Cache/Resource is properly implemented
        port = 80
        if len(urirefs) != 1:
            Params.log("Multiple references %s" % ref)
            continue
        urlparts = urlparse.urlparse(urirefs[0])
        hostname = urlparts.netloc
        pathname = urlparts.path[1:] 
# XXX: cannot reconstruct--, or should always normalize?
        if urlparts.query:
            #print urlparts
            pathname += '?'+urlparts.query
        hostinfo = hostname, port
        cache = get_cache(hostinfo, pathname)
# end
        act = None
        if not check_descriptor(cache, *descr):
            if not Params.PRUNE:
                continue
            act = True
            if cache.full() or cache.partial():
                path = cache.path
                if cache.partial():
                    path += '.incomplete'
                if os.path.getsize(path) > Params.MAX_SIZE_PRUNE:
                    if Params.INTERACTIVE:
                        pass
                    Params.log("Keeping %s" % path)
                    continue
                if os.path.isfile(path):
                    print 'size=', cache.getsize() / 1024**2
                    os.unlink(path)
                    Params.log("Deleted %s" % path)
                else:
                    Params.log("Unable to remove dir %s" % path)
            del descriptors[ref]
            Params.log("Removed %s" % cache.path)
    Params.log("Finished checking %s cache descriptors" % count)
    descriptors.close()
    #pb.clear()
    sys.exit(0)




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


