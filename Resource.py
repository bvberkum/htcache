""" """
import datetime, os, re, anydbm
try:
    # Py >= 2.4
    assert set
except AssertionError:
    from sets import Set as set

import Params, Protocol
from error import *

from gate.util import HeaderDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from taxus.data import initialize, Resource, Locator, ContentDescriptor, \
        Status, Description, Variant, Invariant, Relocated
import uriref

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


class CachedResource(object):

    """

    Represent an entity, consisting of a content-stream,
    a URL, a status, and set of headers.

    A facade in front of:
      - One URI reference (a uriref.URIRef instance)
      - A set of resource properties and other message headers (in a Descriptor
        from a DescriptorStorage instance)
      - A cached resource (a Cache.File instance)

    """

    def __init__(self, resource):
        self.res = resource
        self.__location = None
        super(CachedResource, self).__init__()

    def init(self): pass
        #cache_location = '%s:%i%s' % (self.ref.host, self.ref.port, self.path)
        #self.cache = cache_be(cache_location)
        #self.descriptor = descriptors[cache_location].bind(cache_location, self)
        #return self.cache

    def update(self, status, headers):
        for hn in headers:
            if hn == 'Content-Location':
                url = headers[hn]
            elif hn == 'Content-Type':
                headers[hn]
        #self.headers = HeaderDict(args)
        #if status in (HTTP.OK, HTTP.PARTIAL_CONTENT, HTTP.FOUND, HTTP.MOVED_TEMPORARILY):
        #self.descriptors[self.cache.path] = [self.resource.href], headers

    @property
    def location(self):
        if not self.__location:
            self.__location = uriref.URIRef(self.res.location.ref)
        return self.__location

    @property
    def path(self):
        """Includes query or search part, and fragment. """
        path = self.location.path
        if self.location.query:
            path += '?'+self.location.query
        elif self.location.fragment:
            path += '#'+self.location.fragment
        return path

    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        else:
            return getattr(self.location, name)


def new(request_url, type_=Relocated):
    session = initialize(Params.BACKEND)

    now = datetime.datetime.now()
    locator = Locator(ref=request_url, date_added=now)
    session.add(locator)
    resource = type_(location=locator, date_added=now)
    session.add(resource)
    session.commit()
    return resource

def forRequest(request_url):
    return

    session = initialize(Params.BACKEND)

    resource = session.query(Relocated, Locator)\
        .join('location')\
        .filter(Locator.ref == request_url)\
        .first()

    if resource:
        Params.log("Found Relocated resource at %s" % request_url)
        return CachedResource(resource[0])

    resource = session.query(Variant, Locator)\
        .join('location')\
        .filter(Locator.ref == request_url)\
        .first()

    if resource:
        Params.log("Found Variant resource at %s" % request_url)
        return CachedResource(resource[0])

    resource = session.query(Resource, Locator)\
        .join('location')\
        .filter(Locator.ref == request_url)\
        .first()

    if resource:
        Params.log("Found untyped resource at %s" % request_url)
        return CachedResource(resource[0])




