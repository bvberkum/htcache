""" 
Class for descriptor storage.
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
from error import *



class Storage(object):

    """
    AnyDBM facade.
    To keep descriptor storage and several indices to make it searchable.
    """

    resources = None
    """Web Resources::
    
        { <res> : <Resource(
           
           host, path, meta, cache

        )> }
    """

    brokenmap = None
    """Map of broken loations that could not be retrieved::

        { <res> : <status> }
    """

    descriptors = None
    """Cache descriptors::
    
        { <path> : <Descriptor(
            
            hash, mediatype, charset, language, size, quality

        ) }
    """

    cachemap = None
    """Map of uriref to cache locations (reverse for resources)::
    
        { <path> : <res> }
    """

    relations_to = None
    """Qualified relations 'rel' from 'res' to 'ref'::

        relations_to = { <res> => *( <rel>, <ref> ) }
    """
    relations_from = None
    """Reverse mapping, the qualification will be in relations_to::

        relations_from = { <ref> => *<res> }
    """

    def __init__(self, resources, descriptors, cachemap, resourcemap):

        Params.log([
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
        return self.find(path)

    def find(self, path):
        if path not in self.__descriptors:
            if path in self.descriptors:
                self.__descriptors[path] = self.descriptors[path]
            else:
                return
        return self.__descriptors[path]

    def prepare_for_request(self, path, request):
        if path in self.__descriptors:
            return self.__descriptors[path]
        # XXX: work in progress

        descr = Descriptor( self )
        if request.uriref in self.descriptors:
            descr.load_from_storage( uriref )
        self.__descriptors[uriref] = descr

        res = HTTP.map_headers_to_resource( args )
        HTTP.map_headers_to_descriptor( args )
        res['cache'] = path
        assert path not in self.storage.descriptors
        self.path = path
        self.commit()

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

    def __init__( self, storage ):
        self.path = None
        self.__res_data = {}
        self.__descr_data = {}
        self.__res_data = {}
        self.storage = storage

    def __nonzero__( self ):
        return self.path != None

    def load_from_storage( self, path ):
        self.path = path
        self.__data = Params.json_read(
                self.storage.descritors[self.path])
        Params.log(['load_from_storage', self.path, self.__data]);

    def commit( self ):
        assert self.path
        self.storage.descriptors[self.path] = Params.json_write(
                self.__data)
        Params.log([ 'commit', path, self.__data ], 4)

    def update(self, args):
        newdata = HTTP.map_headers_to_resource(args)
        for k in newdata:
            assert k in self.__data,\
                    "Update to unknown header: %r" % k
            assert newdata[k] == self.__data[k], \
                    "XXX: update"
        Params.log([ 'update', self.path, args, self.__data ], 4)
        self.__data.update(newdata)

    def drop(self):
        del self.storage.descriptors[self.path]
        Params.log([ 'drop', self.path, self.__data ], 4)

    def create_for_response(self, protocol, response):
        assert False
        raise "TODO"

    @property
    def data(self):
        return self.__data

    def set_broken(self):
        raise "TODO"


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
        Params.log("Opening %s mode=%s" %(path, mode))
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
        
    path = Params.DATA_DIR

    mode = 'w'
    if read_only:
        mode = 'r'

    backend = Storage(**dict(
            resources=(join(path, 'resources.db'), mode),
            descriptors=(join(path, 'descriptors.db'), mode,),
            cachemap=(join(path, 'cache_map.db'), mode),
            resourcemap=(join(path, 'resource_map.db'), mode,)
        ))

def get_backend(read_only=False):
    global backend
    if not backend:
        open_backend(read_only)
# FIXME: should know if opened backend is read or write
#    if read_only:
#        assert backend.mode = 'r'
    return backend


# FIXME: rewrite this to Rules or Cmd

# psuedo-Main: special command line options allow resource DB queries:

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
            Params.log("Unknown cache location: %s" % path, Params.LOG_CRIT)
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
    Params.log("End of printinfo", Params.LOG_DEBUG)
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
    Params.log("End of findinfo", Params.LOG_DEBUG)
    sys.exit(1)

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
    global backend
# XXX old
    #if Params.PRUNE:
    #    descriptors = get_backend()
    #else:
    #    descriptors = get_backend(main=False)
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
            if f not in backend.descriptors:
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
            elif f in backend.descriptors:
                rcount += 1
                descr = backend.descriptors[f]
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
    backend.close()
    sys.exit(0)

def check_cache():
    #term = Resource.TerminalController()
    #print term.render('${YELLOW}Warning:${NORMAL}'), 'paper is crinkled'
    #pb = Resource.ProgressBar(term, 'Iterating descriptors')
#    if Params.PRUNE:
#        descriptors = get_backend()
#    else:
#        descriptors = get_backend(main=False)
    global backend
    refs = backend.descriptors.keys()
    count = len(refs)
    Params.log("Iterating %s descriptors" % count)
    for i, ref in enumerate(refs):
        Params.log("%i, %s" % (i, ref), Params.LOG_DEBUG)
        descr = backend.descriptors[ref]
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
            del backend.descriptors[ref]
            Params.log("Removed %s" % cache.path)
    Params.log("Finished checking %s cache descriptors" % count)
    backend.close()
    #pb.clear()
    sys.exit(0)


