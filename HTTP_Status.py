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
