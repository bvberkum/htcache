""" """
import os, re, anydbm

try:
    # Py >= 2.4
    assert set
except AssertionError:
    from sets import Set as set

import Params

# XXX dont use cjson, its buggy, see comments at
# http://pypi.python.org/pypi/python-cjson
# use jsonlib or simplejson
try:
    #import cjson as json
    #json_read = json.decode
    #json_write = json.encode
    import simplejson as _json
except:
    import json as _json


json_read = _json.loads
json_write = _json.dumps

URL_SCHEMES = ['ftp', 'http']


def strip_root(path):
    if path.startswith(Params.ROOT):
        path = path[len(Params.ROOT):]
    if path.startswith(os.sep):
        path = path[1:]
    return path

# descriptor storages:

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
    def close(self): pass
    def update(self, hrds): pass


class AnyDBStorage(DescriptorStorage):

    def __init__(self, path):
        if not os.path.exists(path):
            try:
                anydbm.open(path, 'n').close()
            except Exception as e:
                raise Exception("Unable to create new resource DB at <%s>: %s" %
                        (path, e))
        try:
            self.__be = anydbm.open(path, 'rw')
        except anydbm.error, e:#bsddb.db.DBAccessError, e:
            raise Exception("Unable to access resource DB at <%s>: %s" % 
                    (path, e))

    def close(self):
        self.__be.close()

    def keys(self):
        return self.__be.keys()

    def __iter__(self):
        return iter(self.__be)

    def __contains__(self, path):
        path = strip_root(path)
        return path in self.__be

    def get(self, path):
        data = self.__be[path]
        value = tuple(json_read(data))
        return Descriptor(value, be=self)

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
        self.__be[path] = json_write((srcrefs, mt, cs, ln, metadata, features))
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

Params.BACKENDS.update(dict(
        # TODO: filestorage not implemented
        file= (lambda p: os.path.isdir(p), FileStorage),
        anydb= (_is_db, AnyDBStorage),
        sql= (_is_sql, RelationalStorage)
    ))

def init_backend(request, be=Params.BACKEND):

    for name in Params.BACKENDS:
        if Params.BACKENDS[name][Params.BD_IDX_TEST](be):
            return Params.BACKENDS[name][Params.BD_IDX_TYPE](be)

    raise Exception("Unable to find backend type of %r" % be)


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
    sys.exit(1)

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

if Params.PRINT_ALLRECORDS:
    print_info(*backend.keys())
elif Params.PRINT_RECORD:
    print_info(*Params.PRINT_RECORD)
elif Params.FIND_RECORDS:
    find_info(Params.FIND_RECORDS)
elif Params.PRINT_MEDIA:
    print_media_list(*Params.PRINT_MEDIA)


