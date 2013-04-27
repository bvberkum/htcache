Cache Control

Applies to HTTP 1.1 if not explicit.

   - Also: http://www.askapache.com/seo/advanced-http-redirection.html  

----

From RFC 2616:

Authentication
    Requests with Authenticate header, if Response Cache-Control is:
    
    s-cache:
        May serve non-expired cache, otherwise revalidate.
    must-revalidate:
        May cache and serve while fresh.
        Use new request to revalidate.
    public
        May cache and serve. XXX: while fresh?
        
Authenticate
    Requests with authentication header

Three kinds of client cache control actions:
    End-to-end reload    
        Cache-Control contains no-cache (or Pragma: is no-cache for HTTP 1.0)
    Specific end-to-end revalidation
    Unspecific end-to-end-revalidation

Using directives:
    max-age

----

Accept-Ranges
    - Sometimes the server reports this while the proxy does not.
      See tests.
