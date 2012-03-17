""" """
import os, re, anydbm


try:
    # Py >= 2.4
    assert set
except AssertionError:
    from sets import Set as set

import Params
#from script_mpe import res
#from script_mpe.res import PersistedMetaObject


class DescriptorStorage(object):

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


# descriptor storages:

class FileStorage(object):
    def close(self): pass
    def update(self, hrds): pass


class AnyDBStorage(object):

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

    def __contains__(self, path):
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

    def has(self, path):
        return path in self.__be

    def get(self, path):
        return tuple(Params.json_read(self.__be[path]))

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
    backend =  FileStorage(Params.RESOURCES)

elif Params.RESOURCES.endswith('.db'):
    backend =  AnyDBStorage(Params.RESOURCES)

def get_backend():
    return backend



# special command line options allow resource DB queries:

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

#DescriptorStorage(Params.DATA_DIR)
