""" 
Class for descriptor storage.
"""
import anydbm, datetime, os, re, urlparse
from os.path import join


try:
    # Py >= 2.4
    assert set
except AssertionError:
    from sets import Set as set

import Params
import HTTP
from error import *

#import uriref
import Params, Cache



class Storage(object):

    """
    AnyDBM facade.
    """

    resources = None
    """Shelved resource objects::
    
        resources = { <res> => <Resource:{
           
           host, path, meta, cache

        }> }
    """

    descriptors = None
    """Shelved descriptor objects::
    
        descriptors = { <path> => <Descriptor:{
            
            hash, mediatype, charset, language, size, quality

        }> }
    """

    cachemap = None
    """Map of uriref to cache locations (forward)::
    
        cachemap = { <res> => <path> }
    """

    resourcemap = None
    "Map of cache location to uriref (reverse). "

    relations_to = None
    """
    Qualified relations 'rel' from 'res' to 'ref'::

        relations_to = { <res> => *( <rel>, <ref> ) }
    """
    relations_from = None
    """Reverse mapping::

       relations_from = { <ref> => *<res> }
    """

    def __init__(self, resources, descriptors, cachemap, resourcemap):

        Params.log([
            resources,
            descriptors, 
            cachemap,
            resourcemap
        ])
        self.resources = self.ResourceStorageType(*resources)
        self.descriptors = self.DescriptorStorageType(*descriptors)
        self.cachemap = self.CacheMapType(*cachemap)
        self.resourcemap = self.ResourceMapType(*resourcemap)

        self.__resources = {}
        self.__descriptors = {}
        # XXX:
        #chksmdb = join(path, '.cllct/sha1sum.db')
        #self.sha1sum = dbshelve.open(chksmdb)

    def close(self):
        self.resource.close()
        self.descriptors.close()
        self.cachemap.close()
        self.resourcemap.close()

    def get_descriptor(self, path):
        if path in self.__descriptors:
            return self.__descriptors[path]
        descr = Descriptor(self)
        if path not in self.descriptors:
            if os.path.exists(path):
                Params.log("Data loss recovery: unexpected cache location: %r" % path)
        else:
            descr.load_from_storage(path)
        self.__descriptors[path] = descr
        return descr

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

    def __init__(self, storage):
        self.path = None
        self.__data = {}
        self.storage = storage

    def __nonzero__(self):
        return self.path != None

    def init(self, path, args):
        self.__data = HTTP.map_headers_to_resource(args)
        self.path = path
        assert self.path not in self.storage.descriptors
        self.storage.descriptors[self.path] = Params.json_write(
                self.__data)
        Params.log([ path, self.__data ], 4)

    def update(self, args):
        newdata = HTTP.map_headers_to_resource(args)
        for k in newdata:
            assert k in self.__data,\
                    "Update to unknown header: %r" % k
            assert newdata[k] == self.__data[k], \
                    "XXX: update"
        Params.log([ 'update', self.path, args, self.__data ], 4)
#        for k in self.__data:
#            assert k in newdata, \
#                    "Missing update to %r" % k
        # XXX: self.__data.update(newdata)

    def drop(self):
        del self.storage.descriptors[self.path]
        Params.log([ 'drop', self.path, self.__data ], 4)

    def load_from_storage(self, path):
        self.path = path
        self.__data = Params.json_read(
                self.storage.descritors[self.path])
        Params.log(['load_from_storage', self.path, self.__data]);

    def create_for_response(self, protocol, response):
        pass

    @property
    def data(self):
        return self.__data

#    def __getitem__(self, idx):
#        if idx >= len(self.data):
#            raise IndexError()
#        #if idx < len(self.data):
#        return self.__data[idx]
#
#    def __setitem__(self, idx, value):
#        self.__data[idx] = value
#
#    def __contains__(self, key):
#        return key in self.__data
#
#    def __iter__(self):
#        return iter(self.__data)
#
#    def commit(self):
#        pass


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

    def set_(self, path, srcrefs, headers):
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
        """
        Merge srcrefs, headers.
        """
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

def index_factory(storage, path, mode='w'):

    if not os.path.exists(path):
        assert 'w' in mode
        try:
            anydbm.open(path, 'n').close()
        except Exception, e:
            raise Exception("Unable to create new resource DB at <%s>: %s" %
                    (path, e))
    try:
        Params.log("Opening %s mode=%s" %(path, mode))
        return anydbm.open(path, mode)
    except anydbm.error, e:
        raise Exception("Unable to access resource DB at <%s>: %s" %
                (path, e))

Storage.ResourceStorageType = index_factory
Storage.DescriptorStorageType = index_factory
Storage.ResourceMapType = index_factory
Storage.CacheMapType = index_factory


storage = None

def open_backend():
    
    global storage
        
    path = Params.DATA_DIR

    storage = Storage(**dict(
            resources=(join(path, 'resources.db'),),
            descriptors=(join(path, 'descriptors.db'),),
            cachemap=(join(path, 'cache_map.db'),),
            resourcemap=(join(path, 'resource_map.db'),)
        ))


def for_request(request):

    global storage

    cache = get_cache(request.hostinfo, request.envelope[1])
    descriptor = storage.get_descriptor(cache.path) 

    if descriptor and not (cache.full() or cache.partial()):
        Params.log("Warning: stale descriptor")
        descriptor.drop()

    elif not descriptor and (cache.full() or cache.partial()):
        Params.log("Error: stale cache %s" % cache.path)
        # XXX: should load new Descriptor into db here or delete stale files.

    return cache, descriptor


# XXX: rewrite to New backend
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





# XXX: rewrite this to Rules or Cmd


# psuedo-Main: special command line options allow resource DB queries:

def print_info(*paths):
    import sys
    recordcnt = 0
    descriptors = get_backend()
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
    global backend
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


