"""
Resource storage and descriptor facade.
"""
import anydbm, os, urlparse
from os.path import join

try:
    # Py >= 2.4
    assert set
except AssertionError:
    from sets import Set as set

import Params
import HTTP
import Rules
import Runtime
from util import *
from error import *



class Storage(object):

    """
    AnyDBM facade for several indices.
    To keep descriptor storage and several indices to make it searchable.
    """

    resources = None
    """Web Resources::

        { <res-uri> : <Resource(

           host, path, meta, cache

        )> }
    """

    brokenmap = None
    """Map of broken loations that could not be retrieved::

        { <res-uri> : <status>, <keep-boolean> }
    """

    descriptors = None
    """Cache descriptors::

        { <cache-location> : <Descriptor(

            hash, mediatype, charset, language, size, quality

        ) }
    """

    cachemap = None
    """Map of uriref to cache locations (reverse for resources)::

        { <cache-location> : <res-uri> }
    """

    relations_to = None
    """Qualified relations 'rel' from 'res' to 'ref'::

        relations_to = { <res-uri> => *( <rel-uri>, <ref-uri> ) }
    """
    relations_from = None
    """Reverse mapping, the qualification will be in relations_to::

        relations_from = { <ref-uri> => *<res-uri> }
    """

    def __init__(self, resources, descriptors, cachemap, resourcemap):

        log([
            resources,
            descriptors,
            cachemap,
            resourcemap
        ])
        self.resources = self.ResourceStorageFactory(*resources)
        self.descriptors = self.DescriptorStorageFactory(*descriptors)
        self.cachemap = self.CacheMapFactory(*cachemap)
        self.resourcemap = self.ResourceMapFactory(*resourcemap)

        self.__resources = {}
        self.__descriptors = {}
        # XXX:
        #chksmdb = join(path, '.cllct/sha1sum.db')
        #self.sha1sum = dbshelve.open(chksmdb)

    def close(self):
        self.resources.close()
        self.descriptors.close()
        self.cachemap.close()
        self.resourcemap.close()

    def __contains__(self, path):
        return self.find(path) != None

    def fetch(self, url):
        res = self.find(url)
        if not res:
            raise Exception("No record for %s" % url)
        return res

    def find(self, uriref):
        if uriref not in self.__resources:
            if uriref in self.resources:
                res = Resource(self).load(uriref)
                self.__resources[uriref] = res
            else:
                return
        return self.__resources[uriref]

    def prepare(self, protocol):
        uriref = protocol.url
        if uriref in self.__resources:
            return self.__resources[uriref]
        res = Resource(self)
        if uriref in self.resources:
            res = Resource(self).load(uriref)
        res.update(protocol.headers)
        self.__resources[uriref] = res
        return res

    def put(self, uriref, metalink):
        """
        Store or update the descriptor.
        """
        self.shelve[uriref]
        if uriref in self.cachemap:
            self.cache[uriref]
        pass

    def set(self, uriref, descriptor):
        pass

    def __setitem__(self, path, value):
        self.shelve


### Descriptor Storage types:

class Record(object):
    def __init__(self, storage):
        super(Record, self).__init__()
        self.__data = {}
        self.storage = storage

    def __setitem__(self, key, value):
        self.__data[key] = value

    def __getitem__(self, key):
        return self.__data[key]

    def __str__(self):
        return str(self.__data)


class Resource(Record):

    def __init__(self, storage):
        super(Resource, self).__init__(storage)

    def __nonzero__(self):
        return self.path != None

    # FIXME:
    @property
    def new(self):
        return self.path not in self.storage.descriptors

    def load( self, path ):
        self.path = path
        self.__data = json_read(
                self.storage.descritors[self.path])
        log(['load_from_storage', self.path, self.__data])
        return self

    def commit(self):
        assert self.path
        self.storage.descriptors[self.path] = json_write( self.__data )
        log([ 'commit', self.path, self.__data ], Params.LOG_DEBUG)

    def update(self, headers):
        newdata = HTTP.map_headers_to_resource(headers)
        for k in newdata:
            if k.startswith('content.'):
                self.content[k[8:]] = newdata[k]
            else:
                self[k] = newdata[k]
        #for k in newdata:
        #    assert k in self.__data,\
        #            "Update to unknown header: %r" % k
        #    assert newdata[k] == self.__data[k], \
        #            "XXX: update"
        log([ 'update', self.path, args, self.__data ], Params.LOG_DEBUG)
        self.__data.update(newdata)

    def drop(self):
        del self.storage.descriptors[self.path]
        log([ 'drop', self.path, self.__data ], Params.LOG_DEBUG)

    def create_for_response(self, protocol, response):
        assert False
        raise "TODO"

    @property
    def data(self):
        return self.__data

    def set_broken(self, status ):
        # TODO: set_broken
        self.drop()


class Descriptor(Record):
    pass

#/FIXME


def index_factory(storage, path, mode='r'):
    """
    Modes:
        r: read only
        w: read and write, create if needed
    """

    if not os.path.exists(path):
        assert 'w' in mode, "Missing resource DB, no file at <%s>" % path
        try:
            anydbm.open(path, 'n').close()
        except Exception, e:
            raise Exception("Unable to create new resource DB at <%s>: %s" %
                    (path, e))
    try:
        log("Opening %s mode=%s" %(path, mode))
        return anydbm.open(path, mode)
    except anydbm.error, e:
        raise Exception("Unable to access resource DB at <%s>: %s" %
                (path, e))


Storage.ResourceStorageFactory = index_factory
Storage.DescriptorStorageFactory = index_factory
Storage.ResourceMapFactory = index_factory
Storage.CacheMapFactory = index_factory


backend = None

def open_backend(read_only=False):
    global backend

    assert Runtime.DATA_DIR
    path = Runtime.DATA_DIR

    mode = 'w'
    if read_only:
        mode = 'r'

    backend = Storage(**dict(
            resources=(join(path, 'resources.db'), mode),
            descriptors=(join(path, 'descriptors.db'), mode,),
            cachemap=(join(path, 'cache_map.db'), mode),
            resourcemap=(join(path, 'resource_map.db'), mode,)
        ))
    backend.mode = mode

def get_backend(read_only=False):
    global backend
    if not backend:
        open_backend(read_only)
    if read_only:
        assert backend.mode == 'r'
    return backend

def close_backend():
    global backend
    backend.close()
    backend = None



def list_locations():
    global backend
    get_backend(True)
    print backend.resources
    print backend.descriptors
    for path in backend.descriptors:
        print path
    backend.close()

def list_urls():
    global backend
    get_backend(True)
    for url in backend.resources:
        res = backend.find(url)
        print res

def print_record(url):
    backend = get_backend(True)
    res = backend.fetch(url)
    print res

# TODO: find_records by attribute query
def find_records(q):
    import sys
    global backend
    print 'Searching for', q

    attrpath, valuepattern = q.split(':')

    for path in backend:
        res = backend[path]
        urls, mime, qs, n, meta, feats = res
        for u in urls:
            if q in u:
                print path, mime, urls
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
    log("End of findinfo", Params.LOG_DEBUG)

# TODO: integrate with other print_info
def print_info(*paths):
    global backend
    open_backend(True)
    import sys
    recordcnt = 0
    for path in paths:
        if not path.startswith(os.sep):
            path = Params.ROOT + path
#        path = path.replace(Params.ROOT, '')
        if path not in backend:
            log("Unknown cache location: %s" % path, Params.LOG_CRIT)
        else:
            print path, backend.find(path)
            recordcnt += 1
    if recordcnt > 1:
        print >>sys.stderr, "Found %i records for %i paths" % (recordcnt,len(paths))
    elif recordcnt == 1:
        print >>sys.stderr, "Found one record"
    else:
        print >>sys.stderr, "No record found"
    backend.close()
    log("End of printinfo", Params.LOG_DEBUG)

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
        log("Missing %s" % pathname)
        return
    if 'Content-Length' not in meta:
        log("Missing content length of %s" % pathname)
        return
    length = int(meta['Content-Length'])
    if cache.full() and os.path.getsize(pathname) != length:
        log("Corrupt file: %s, size should be %s" % (pathname, length))
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

def check_files():
    backend = get_backend(True)
# XXX old
    #if Params.PRUNE:
    #    descriptors = get_backend()
    #else:
    #    descriptors = get_backend(main=False)
    pcount, rcount = 0, 0
    log("Iterating paths in cache root location. ")

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
            if f not in backend.descriptors:
                if os.path.isfile(f):
                    log("Missing descriptor for %s" % f)
                    if Runtime.PRUNE:
                        size = os.path.getsize(f)
                        if size < Runtime.MAX_SIZE_PRUNE:
                            os.unlink(f)
                            log("Removed unknown file %s" % f)
                        else:
                            log("Keeping %sMB" % (size / (1024 ** 2)))#, f))
                elif not (os.path.isdir(f) or os.path.islink(f)):
                    log("Unrecognized path %s" % f)
            elif f in backend.descriptors:
                rcount += 1
                descr = backend.descriptors[f]
                assert isinstance(descr, Record)
                uriref = descr[0][0]
                log("Found resource %s" % uriref, threshold=1)
# XXX: hardcoded paths.. replace once Cache/Resource is properly implemented
                port = 80
                if len(descr[0]) != 1:
                    log("Multiple references %s" % f)
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
    log("Finished checking %s cache locations, found %s resources" % (
        pcount, rcount))
    backend.close()

def check_cache():
    #term = Resource.TerminalController()
    #print term.render('${YELLOW}Warning:${NORMAL}'), 'paper is crinkled'
    #pb = Resource.ProgressBar(term, 'Iterating descriptors')
#    if Params.PRUNE:
#        descriptors = get_backend()
#    else:
#        descriptors = get_backend(main=False)
    backend = get_backend(True)

    refs = backend.descriptors.keys()
    count = len(refs)
    log("Iterating %s descriptors" % count)
    for i, ref in enumerate(refs):
        log("%i, %s" % (i, ref), Params.LOG_DEBUG)
        descr = backend.descriptors[ref]
        log("Record data: [%s] %r" %(ref, descr.data,), 2)
        urirefs, mediatype, d1, d2, meta, features = descr
        #progress = float(i)/count
        #pb.update(progress, ref)
# XXX: hardcoded paths.. replace once Cache/Resource is properly implemented
        port = 80
        if len(urirefs) != 1:
            log("Multiple references %s" % ref)
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
                    log("Keeping %s" % path)
                    continue
                if os.path.isfile(path):
                    print 'size=', cache.getsize() / 1024**2
                    os.unlink(path)
                    log("Deleted %s" % path)
                else:
                    log("Unable to remove dir %s" % path)
            del backend.descriptors[ref]
            log("Removed %s" % cache.path)
    log("Finished checking %s cache descriptors" % count)
    backend.close()
    #pb.clear()


