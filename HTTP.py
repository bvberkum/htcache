


class HTTP:

    OK = 200
    PARTIAL_CONTENT = 206
    MULTIPLE_CHOICES = 300 # Variant resource, see alternatives list
    MOVED_PERMANENTLY = 301 # Located elsewhere
    FOUND = 302 # Moved permanently
    SEE_OTHER = 303 # Resource for request located elsewhere using GET
    NOT_MODIFIED = 304
    #USE_PROXY = 305
    _ = 306 # Reserved (no longer used)
    TEMPORARY_REDIRECT = 307 # Same as 302,
    # added to explicitly contrast with 302 mistreated as 303

    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    #PROXY_AUTH_REQUIRED = 407
    #REQUEST_TIMEOUT = 408
    #CONFLICT = 409
    GONE = 410
    REQUEST_RANGE_NOT_STATISFIABLE = 416

    Entity_Headers = (
        # RFC 2616
        'Allow',
        'Content-Encoding',
        'Content-Language',
        'Content-Length',
        'Content-Location',
        'Content-MD5',
        'Content-Range',
        'Content-Type',
        'Expires',
        'ETag',
        'Last-Modified',
    # extension-header
    )
    Request_Headers = (
        'Cookie',
        # RFC 2616
        'Accept',
        'Accept-Charset',
        'Accept-Encoding',
        'Accept-Language',
        'Authorization',
        'Expect',
        'From',
        'Host',
        'If-Match',
        'If-Modified-Since',
        'If-None-Match',
        'If-Range',
        'If-Unmodified-Since',
        'Max-Forwards',
        'Proxy-Authorization',
        'Range',
        'Referer',
        'TE',
        'User-Agent',
        # RFC 2295
        'Accept-Features',
        'Negotiate',
    )
    Response_Headers = (
        'Via',
        'Set-Cookie',
        'Location',
        'Transfer-Encoding',
        'X-Varnish',
        # RFC 2616
        'Accept-Ranges',
        'Age',
        'Location',
        'Proxy-Authenticate',
        'Retry-After',
        'Server',
        'Vary',
        'WWW-Authenticate',
        # RFC 2295
        'Alternates',
        'TCN',
        'Variant-Vary',
        # ???
        'Srv',
        'P3P',
    )
    Cache_Headers = ( # Cachable stuff beyond entity?
    )


    Message_Headers = Request_Headers + Response_Headers +\
            Entity_Headers + \
            Cache_Headers + (
                    # Generic headers
                    # RFC 2616
                    'Date',
                    'Cache-Control', # RFC 2616 14.9
                    'Pragma', # RFC 2616 14.32
                    'Proxy-Connection',
                    'Proxy-Authorization',
                    'Connection',
                    'Keep-Alive',
                    # Extension and msc. unsorted headers
                    'X-Server',
                    'X-Cache',
                    'X-Cache-Lookup',
                    'X-Cache-Hit',
                    'X-Cache-Hits',
                    'X-Content-Type-Options',
                    'X-Powered-By',
                    'X-Relationship', # used by htcache
                    'X-Id',
                    'X-Varnish',
                    'Status',
                    'X-AspNet-Version',
                    'Origin',
                    'X-Requested-With',
                    'Content-Disposition',
                    'X-Frame-Options',
                    'X-XSS-Protection',
                    'VTag',
# nujij.nl
                    'X-Served-By',
                    'X-Age', # nujij.nl
                    'X-Request-Backend', # nujij.nl
                    'X-KUID',
                    'X-N',
                    'X-Request-Time',
# ebay
                    'RlogId',
                )
    """
    For information on other registered HTTP headers, see RFC 4229.
    """

    # use these lists to create a mapping to retrieve the properly cased string.
    Header_Map = dict([(k.lower(), k) for k in Message_Headers ])

def filter_entity_headers(headers):
    for k in headers.keys():
        if k not in HTTP.Entity_Headers:
            del headers[k]
    return headers

