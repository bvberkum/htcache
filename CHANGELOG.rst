TODO htcache version 1.0 (planned)
  * Tested FTP use.
  * RFC 2616 adherence.
  * On-line cache maintenance.  
  * Static browsing of cached resources.  
  * Multiple mechanisms to reduce content duplication.
  * Filter content using URL regex matching.  
  * Keep favicon until user approves changes, set custom favicons.
  * In-browser JS control served with (x)HTML resources to allow 
    in-navigation proxy operations on the current resource.
  * Keep version and navigation history for certain resources.

2012-03-14 htcache version 0.9 
2012-03-14 htcache version 0.8 
2012-03-14 htcache version 0.7 
2012-03-14 htcache version 0.6 
2012-03-14 htcache version 0.5 
2012-03-14 htcache version 0.4 (development)
  * All this time forgot to bump version number.
  * Capture: Re-introduce content hashing but only for specific resources.
    Track history by these checksums, and also track X-Relationship (nav)
    relations between them.
  * Proc: implement idea to defer processing to external script.
    Makes for a very dirty HTTP proxy triggered workflow. 

2010-09-28 htcache version 0.3 (mpe)
  * Many changes and a bit of history corruption in the branches, I made a mess
    of it but as of now most tests pass again. Development went on in too many
    disparate directions and I didn't handle that well.
  * However some new tests were created and most of the tests are passing.
    FTP support has not returned yet.
  * NoCache and Drop are working as before (cache bypass and request blocker)
  * Join has been added to rewrite URL's (effectively joining them if possible with
    existing downloads). This works to reduce duplication for known URLs.
  * Mapping known headers to proper case.

2010-09-28 htcache version 0.2 (mpe)
  * rename to htcache
  * added support for alternative cache directory layouts using modular 
    cache backends  
  * added descriptor cache for resource metadata  
  * allow simple queries on resource metadata  
  * added support to block request based on URL matching
  * added fancy html and image placeholder for blocked requests  
  * added support to bypass cache based on URL matching
  * created Sys-V init sh script
  * including HTTP Via header
  * Updated Makefile for tar'ed dists and incremental snapshots.
  * various more changes from the past two years, see revision log

2008-31-01 http-replicator version 4.0alpha2
  * added GPL licence file
  * generalized fiber.py by using generator name instead of hardcoded string
  * removing partial file in cache after 403 forbidden
  * flushing every line in debug mode
  * fix: no longer setting mtime to -1 if server does not send Last-Modified
  * fix: handling empty command lines correctly

2008-01-01 http-replicator version 4.0alpha1
  * rewrite from scratch
  * replaced restrictive asyncore scheduler with new 'fiber' system
  * new feature: server-side download resuming
  * new feature: fpt support
  * new feature: bandwidth shaping
  * new feature: ipv6 support
  * new feature: frozen transactions killed after configurable timeout
  * new feature: rudimentary off-line mode
  * fixed race condition that prevented joining of simultaneously started downloads
  * currently missing feature: cache browsing

2004-11-27 http-replicator version 3.0
  * new feature: cache brower on proxy address
  * new feature: client-side support for partial content
  * added alias option for caching mirrors on same location
  * added check to prevent access outside of cache through symlinks
  * added header length restriction to fight infinite request server attacks
  * created man pages for http-replicator and http-replicator_maintenance
  * fixed timestamp bug; files are now properly closed before changing mtime
  * suppressed size warning for chunked data

2004-08-15 http-replicator version 2.1
  * integrated daemon code in http-replicator
  * changed init.d and cron script to bash
  * moved settings from configuration file to /etc/default/http-replicator
  * introduced optparse module for command line parsing
  * introduced logging module for output
  * added support for an external proxy server
  * added support for an external proxy requiring authentication

2004-05-01 http-replicator version 2.0
  * added support for HTTP/1.1
  * replicator is now suitable for maintaining a gentoo package cache
  * fixed problem with absolute urls
  * added posting support
  * added support for servers that use LF in header instead of CRLF
  * added a command line system
  * fixed security issues
  * improved traceback message for unhandled exceptions
  * fixed problem with incomplete files after a server crash
  * fixed problems with select
  * fixed size calculation in cron script

2004-02-06 http-replicator version 1.0
  * initial release.

