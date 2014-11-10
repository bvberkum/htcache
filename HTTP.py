from HTTP_Status import *


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
				'X-HTCache-SystemTest', # used by htcache
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
	"""
	Given headers, unset all non-entity headers.
	"""
	for k in headers.keys():
		if k not in Entity_Headers:
			del headers[k]
	return headers

def parse_content_range(content_range_spec):
	"""
	Return the start and and byte position as integer from the given 
	Content-Range header. Must be a 'bytes' range-type of spec (the only one RFC
	2616 gives).
	"""
	bytes_unit, byte_content_range_spec = content_range_spec.split(' ')
	assert bytes_unit == 'bytes'
	bytes_range_response_spec, instance_length = byte_content_range_spec.split('/')
	if bytes_range_response_spec.isdigit():
		bytes_range_response_spec = int(bytes_range_response_spec)
	if instance_length.isdigit():
		instance_length = int(instance_length)
	else:
		assert instance_length == '*'
	return bytes_range_response_spec, instance_length

