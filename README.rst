:parent project: http://freshmeat.net/projects/http-replicator
:homepage: http://github.com/dotmpe/htcache 

.. contents::

**htcache** aims to be a versatile caching and rewriting HTTP and FTP proxy.
It is a fork of http-replicator 4.0 alpha 2. See CHANGELOG.

Todo
 - test FTP use.
 - (auto) remove descriptors after manual path delete.
 - use strict and other modes, adhere to RFC 2616:

    - calculate Age field [14.6]  
    - don't cache Authorization response [14.8]
    - Cache-Control [14.9]

Issues
 1. Writing to client fails randomly, probably dropped connection 
    (eg. cancelled mouseovers)
 2. Some date headers in the wild still fail to parse.
 3. HTML placeholder served for all connections (e.g. also for flash, images)
 4. There is a version with other cl-options, it uses stdlib asyncore
    check: 
 
     * http://web.archive.org/web/20070816213819/gertjan.freezope.org/replicator/http-replicator
     * http://web.archive.org/web/20071214200800/gertjan.freezope.org/replicator
  
 5. Reinstate use of unit-test?   

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
                                o <------------*request---  client
                                |
                                |---blocked response(1)--->
                                |---static response(7)---->
   server <------------normal---|
          <------*conditional---' 
           --*normal----------> o
                                |--*normal----------------> 
                                `--*nocache response(4)---> 
           ---not modified----> o--*cached response------->       
           ---error-----------> o---direct response------->       

   * indicates wether there may be partial entity-content transfer


Normally a request creates a new cache location and descriptor, static 
responses are always served from cache and conditional requests may be.

Beside these messages, also note the following special cases of request 
and response messages.

1. blocked response                                  (rules.drop)
4. blind response (uncached content)                 (rules.nocache)

See the section `Rule Syntax`_ for the exact syntax.


Configuration
~~~~~~~~~~~~~
There is no separate configuration file, see Params.py and init.sh for 
option arguments to the program, and for their default settings. Other settings
are given in the rewrite and rules files described above.

The programs options are divided in three parts, the first group affects 
the proxy server, which is the default action.

To manage the cached resources and their descriptors, additional
query and maintenance options are provided. Note that maintenance may need
exclusive write access to the cache and descriptor backends, meaning don't run
with active proxy.

Cache backends listing
~~~~~~~~~~~~~~~~~~~~~~
htcache uses a file-based Cache which may produce a file-tree similar to 
that of ``wget -r`` (except if ``--nodir`` or ``--archive`` is in effect). 
This can create problems with long filenames and the characters that appear 
in the various URL parts.

Additional backends address this. (default: Cache.File, ``--cache TYPE``)

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

The storage location is futher affected by ``--archive`` and ``--nodir``.

Regular archival of a resources is possible by prefixing a formatted date to
the path. Ie. '%Y/%M/%d' would store a copy and maintain updates of a 
resource for every day. Prefixing a timestamp would probably store a new copy 
for each request.

``--archive`` results in lots of redundant data. It also makes static, offline
proxy operation on the resulting filesystem tree impossible. 

The nodir parameter accepts a replacement for the directory separator and
stores the path in a single filename. This may affect FileTreeQ.

Descriptor backends
~~~~~~~~~~~~~~~~~~~
The descriptor backend (which contains URI, mediatype, charset, language and
other resource-header data) is by default stored in a flat index DB. No
additional backends available at this time.

TODO: a file-based header storage or perhaps even an Apache mod_asis
compatible storage are under consideration. Depending on query/maintenance
requirements.

Rule Syntax
~~~~~~~~~~~
rules.drop::

  # hostpath
  [^/]*zedo\.com.*

Matching DROP rules deny access to the origin server, and instead serve a HTML
or image placeholder.

rules.nocache::

  # hostpath            
  [^/]*gmail\.com.*

A matching NOCACHE rule bypasses the caching for a request, serving directly 
from the origin server or the next proxy on the line.

Both DROP and NOCACHE rule-format will change to include matching on protocol.

rules.sort::

  # proto  hostpath               replacement             root
  *        (.*)                   
  *        [^/]*youtube\.com.*    /my/dir/youtube/\1.flv  mydir/

SORT rules currently prefix the cache-location with a tag, in above example the
location under ROOT will be ``mydir/``. If the ``--archive`` option is in effect
it is prefixed to this tag. Note that ``--nodir`` is applied after prefixing.

This feature is under development.
Rewriting content based on above message matching is planned.

