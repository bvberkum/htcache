:parent project: http://freshmeat.net/projects/http-replicator
:homepage: http://github.com/dotmpe/htcache

**htcache** aims to be a versatile caching and rewriting HTTP and FTP proxy
in Python. It is a fork of http-replicator 4.0 alpha 2. See CHANGELOG.

branches
    master
        - SQL version
        - FIXME: Not working!
        - sqlalchemy integration, trying to use CachedResource (uriref, taxus facade)
        - Proxy restart command
    stable
        - FIXME: Not working!
        - SQL version
        - TODO: contains unused? CachedResource code , integrate or  remove
        - Proxy restart command
    new_stable (current)
        - Tests pass up to FTP tests.
        - anydbm storage
        - Sort, Join and Proc rules in addition to NoCache and Drop.
        - No restart command
    development
        - FIXME: runs somewhat, must make fixes to run all HTTP tests?
        - anydbm storage
        - trying to incoorporate gate.Resource, impl. htache.Resource
    new_development
        - Running.

.. contents::

Status
------
Todo
 - (auto) remove descriptors after manual path delete.
 - use strict and other modes, adhere to RFC 2616:

   - calculate Age field [14.6]
   - don't cache Authorization response [14.8]
   - Cache-Control [14.9]

 - rules.sort prefixes paths
 - would be nice to let addon's provide new rules.
   Ex: user- or community provided favicons.

Issues
 1. Dropped connections/failure to write to client happens, but does not appear
    to be malignant. See Known errors 1.
 2. Some date headers in the wild still fail to parse.
 3. HTML placeholder served for all connections (e.g. also for flash, images)
 4. There is a version with other cl-options, it uses stdlib asyncore
    check:

    * http://web.archive.org/web/20070816213819/gertjan.freezope.org/replicator/http-replicator
    * http://web.archive.org/web/20071214200800/gertjan.freezope.org/replicator

 5. Embedded youtube does not work, but the site runs fine.

Known errors
 1. Writing to client may fail sometimes because of a dropped connection. Ie.
    Google Chrome establishes a pool of connections upon each request to speed
    up browsing, which will time out and close if not used.

Unittests
 No known failures.

Installation
------------
Start as any Python script, or:

- cp/link htcache into ``/usr/bin``
- cp/link ``init.sh`` into ``/dev/init.d/``, modify htcache flags as needed.
  Make sure paths in init.sh and Params.py are accessible.
- add line ``/etc/init.d/htcache start`` to ``/etc/local`` for
  on-startup initialization.

See http://www.debian-administration.org/articles/28 for Debian specifics.

Also create files in /etc/htcache:

* rules.drop
* rules.nocache
* rules.sort

Overview
--------
htcache client/server flow::

   .                         htcache
                             _______

                                o <-------------*get---  client
                                |
                                |---blocked(1)-------->
                                |---static(2)--------->
                                |---direct(3)--------->
   server <------------normal---|
          <------(4)rewritten---|
          <------*conditional---'

           --*normal----------> o
                                ~
           ---rewritten(5)----> o
                                |--*normal------------>
                                |---rewritten(6)------>
                                `--*nocache(7)-------->

           ---not modified----> o--*cached---------------->

           ---error-----------> o---blind----------------->


   * indicates wether there may be partial entity-content transfer


Normally a request creates a new cache location and descriptor, static
responses are always served from cache and conditional requests may be.

Beside these messages, also note the following special cases of request
and response messages.

== ================================================= =======================
                                                     Rules file
-- ------------------------------------------------- -----------------------
1. 'Blocked content' message                         rules.drop
3. Rewritten request message                         rules,filter.req.sort
4. Rewritten response message (cache rewritten)      rules,filter.res.sort
5. Rewritten response message (cache original)       rules,filter.resp.sort
6. Blind response (uncached)                         rules.nocache
== ================================================= =======================

See the section `Rule Syntax`_ for the exact syntax.

Fiber
~~~~~
HTCache is a fork of http-replicator and the main script follows the same
implementation using fibers. It has a bit more elaborated message handling::

   HttpRequest ----> ProxyProtocol --------get--> DirectResponse (3)
                      |            `----nocache-> Blocked(Image)ContentResponse (1)
                      |            `--------ok--> DataResponse
                      |            `--------ok--> RewrittenDataResponse (5,6)
                      `- HttpProtocol ------ok--> (Chunked)DataResponse
                      |               `--error--> BlindResponse
                      `- FtpProtocol -----------> DataResponse
                                     `----------> NotFoundResponse

HttpRequest reads incoming request message and determines the protocol for the
rest of the session. Protocol will wrap the incoming data, the parsed request
header of that data and if needed send the actual message. Upon receiving a
response it parses the message header and determines the appropiate response.

TODO: Rewriting and content filtering is not implemented.

Internal server
~~~~~~~~~~~~~~~
Beside serving in static mode (cached content directly from local storage, w/o
server header), static responses may also include content generated by the proxy
itself.

/echo
    Echo the request message.
/reload
    Reload the server, usefull while writing code.
/htcache.js
    The HTCache DHTML client may expose proxy functionality for retrieved
    content. It is included by setting Params.DHTML_CLIENT.

Configuration
~~~~~~~~~~~~~
There is no separate configuration file, see Params.py and init.sh for
option arguments to the program, and for their default settings. Other settings
are given in the rewrite and rules files described before.

The programs options are divided in three parts, the first group affects
the proxy server, which is the default action.

User/system settings are provided using GNU/POSIX Command Line options. 
These are roughly divided in three parts; the first group affects 
the proxy server, which is the default action. The other two query or process
cached data, and are usefull for maintenance. Note that maintenance may need
exclusive write access to the cache and descriptor backends, meaning don't run
with active proxy.

See ``htcache [-h|--help]``.

Cache backends
______________________
htcache uses a file-based Cache which may produce a file-tree similar to
that of ``wget -r`` (except if ``--nodir`` or ``--archive`` is in effect).
This can create problems with long filenames and the characters that appear
in the various URL parts.

Additional backends can deal with this issue ``--cache TYPE``).
The default backend was Cache.File which is compatible with ``wget -r`` but
is inadequate for general use as web proxy. The new default caches.FileTreeQ
combines some aspects desirable to deal with a wider range of resources.

- caches.FileTreeQ - encodes each query argument into a separate directory,
  the first argument being prefixed with '?'. FIXME: does not solve anything?
- caches.FileTreeQH - Converts query into a hashsum. This one makes a bit more
  sense because queries are not hierarchical. The hashsum is encoded to a
  directory, the name prefixed with '#'.
- caches.PartialMD5 - only encodes the excess part of the filename, the limit
  being hardcoded to 256 characters.
- caches.FileTree - combines above three methods.
- caches.RefHash - simply encodes full URI into MD5 hex-digest and use as
  filename.

Cache options
_______________
The storage location is futher affected by ``--archive`` and ``--nodir``.

Regular archival of a resources is possible by prefixing a formatted date to
the path. Ie. '%Y/%M/%d' would store a copy and maintain updates of a
resource for every day. Prefixing a timestamp would probably store a new copy
for each request.

This option (``--archive FMT``) results in lots of redundant data. It also
makes static, off-line proxy operation on the resulting filesystem tree
impossible.

The nodir parameter accepts a replacement for the directory separator and
stores the path in a single filename. This may affect FileTreeQ.

Descriptor backends
____________________

cache-path <=> uris
cache-path => headers

The descriptor backend (which contains URI, mediatype, charset, language and
other resource-header data) is by default a flat index DB storage.
No additional backends available at this time.

TODO: a file-based header storage or perhaps even an Apache mod_asis
compatible storage are under consideration. Depending on query/maintenance
requirements.


Rule Syntax
~~~~~~~~~~~
rules.drop and rules.nocache::

  # hostpath
  [^/]*expample\.net.*

Matching DROP rules deny access to the origin server, and instead serve a HTML
or image placeholder.

rules.nocache::

  # hostpath
  [^/]*gmail\.com.*

A matching NOCACHE rule bypasses the caching for a request, serving directly
from the origin server or the next proxy on the line.

Both DROP and NOCACHE rule-format will change to include matching on protocol.
Currently, both rules match on hostname and following URL parts only (hence
the [^/] pattern).

rules.{req,res,resp}.sort::

  # proto  hostpath               replacement             root
  *        (.*)                   \1
  *        [^/]*example\.net.*    canonical-example.net   mydir/

SORT rules currently prefix the cache-location with a tag, in above example the
location under ROOT for all content from `youtube.com` will be ``mydir/``. If
the ``--archive`` option is in effect it is prefixed to this tag. (Note that
``--nodir`` is applied *after prefixing*)

filter.{req,res,resp}.filter::

  # mediatype   pattern   replace
  *             (.*)      \1

This feature is under development.
Rewriting content based on above message matching is planned.

