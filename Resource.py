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

from sqlalchemy import Column, Integer, String, Boolean, Text, \
    ForeignKey, Table, Index, DateTime, \
    create_engine
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, sessionmaker

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

    Web Resources::

        { <res-uri> : <Resource(

           host, path, meta, cache

        )> }
    
    Map of broken loations that could not be retrieved::

        { <res-uri> : <status>, <keep-boolean> }
    
    Cache descriptors::

        { <cache-location> : <Descriptor(

            hash, mediatype, charset, language, size, quality

        ) }

    Map of uriref to cache locations (reverse for resources)::

        { <cache-location> : <res-uri> }

    Qualified relations 'rel' from 'res' to 'ref'::

        relations_to = { <res-uri> => *( <rel-uri>, <ref-uri> ) }
    
    Reverse mapping, the qualification will be in relations_to::

        relations_from = { <ref-uri> => *<res-uri> }
    """


### Descriptor Storage types:

SqlBase = declarative_base()


class SessionMixin(object):

    sessions = {}

    @staticmethod
    def get_instance(name='default', dbref=None, init=False, read_only=False):
        # XXX: read_only
        if name not in SessionMixin.sessions:
            assert dbref, "session does not exists: %s" % name
            session = get_session(dbref, init)
            #assert session.engine, "new session has no engine"
            SessionMixin.sessions[name] = session
        else:
            session = SessionMixin.sessions[name]
            #assert session.engine, "existing session does not have engine"
        return session

    @staticmethod
    def close_instance(name='default', dbref=None, init=False, read_only=False):
        if name in SessionMixin.sessions:
            session = SessionMixin.session[name]
        session.close()

    # 
    key_names = []

    def key(self):
        key = {}
        for a in self.key_names:
            key[a] = getattr(self, a)
        return key

    def commit(self):
        session = SessionMixin.get_instance()
        session.add(self)
        session.commit()

    def find(self, qdict=None):
        try:
            return self.fetch(qdict=qdict)
        except NoResultFound, e:
            log("No results for %s.find(%s)" % (cn(self), qdict),
                    Params.LOG_INFO)

    def fetch(self, qdict=None):
        """
        Keydict must be filter parameters that return exactly one record.
        """
        session = SessionMixin.get_instance()
        print qdict
        if not qdict:
            qdict = self.key()
        return session.query(self.__class__).filter(**qdict).one()

    def exists(self):
        return self.fetch() != None 


class Resource(SqlBase, SessionMixin):
    """
    """
    __tablename__ = 'resources'
    id = Column(Integer, primary_key=True)
    host = Column(String(255), nullable=False)
    path = Column(String(255), nullable=False)
    key_names = [id]

class Descriptor(SqlBase, SessionMixin):
    """
    """
    __tablename__ = 'descriptors'
    id = Column(Integer, primary_key=True)
    resource = Column(Integer, ForeignKey(Resource.id), nullable=False)
    path = Column(String(255), nullable=True)
    mediatype = Column(String(255), nullable=False)
    charset = Column(String(255), nullable=True)
    language = Column(String(255), nullable=True)
    size = Column(Integer, nullable=False)
    quality = Column(Integer, nullable=True)
    key_names = [id]

class Relation(SqlBase, SessionMixin):
    """
    """
    __tablename__ = 'relations'
    id = Column(Integer, primary_key=True)
    relate = Column(String(16), nullable=False)
    revuri = Column(Integer, ForeignKey(Resource.id), nullable=False)
    reluri = Column(Integer, ForeignKey(Resource.id), nullable=False)
    key_names = [id]


#/FIXME

backend = None


def get_backend():
    global backend
    backend = SessionMixin.get_instance('default', Params.DATA)


def get_session(dbref, initialize=False):
    engine = create_engine(dbref)#, encoding='utf8')
    #engine.raw_connection().connection.text_factory = unicode
    if initialize:
        log("Applying SQL DDL to DB %s " % (dbref,), Params.LOG_NOTE)
        SqlBase.metadata.create_all(engine)  # issue DDL create 
        print 'Updated schema'
    session = sessionmaker(bind=engine)()
    return session



# Query commands 

def list_locations():
    backend = SessionMixin.get_instance(True, Runtime.DATA)
    print backend.resources
    print backend.descriptors
    for path in backend.descriptors:
        print path
    backend.close()

def list_urls():
    backend = SessionMixin.get_instance(True, Runtime.DATA)
    for url in backend.resources:
        res = backend.find(url)
        print res

def print_record(url):
    backend = SessionMixin.get_instance(True, Runtime.DATA)
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
    backend = SessionMixin.get_instance(True)
# XXX old
    #if Params.PRUNE:
    #    descriptors = SessionMixin.get_instance()
    #else:
    #    descriptors = SessionMixin.get_instance(main=False)
    pcount, rcount = 0, 0
    log("Iterating paths in cache root location. ")

    for root, dirs, files in os.walk(Params.ROOT):

        # Ignore files in root
        if not root[len(Params.ROOT):]:
            continue

#        rdir = os.path.join(Params.ROOT, root)
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
#        descriptors = SessionMixin.get_instance()
#    else:
#        descriptors = SessionMixin.get_instance(main=False)
    backend = SessionMixin.get_instance(True)

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


