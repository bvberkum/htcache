Two to three separate filesystem trees are kept beneath the cache root.

- SHA1 hashing during new resource fetch

::  

    /var/
      cache/
        sha1/
          <sha1sum>        Resource Contents
        urimd5/      
          <md5sum>/*       Timestamped symlink to contents
          <md5sum>.uriref  (optional) Normalized URI
          <md5sum>.headers (optional) As-is header storage
        archive/
          
        www/*              wget -r tree symlinking to urimd5

The first two are always applied. Storing uriref and headers could be optional.
For queries it may be nice to create indices in flat db's.
The wget tree is applied for all compatible URIs, ie. those < 256 chars.
  
XXX: could a deeper tree be created by symlinking? think so..

