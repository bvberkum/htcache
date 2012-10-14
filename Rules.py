import os
import re

import Params


def parse_droplist(fpath=Params.DROP_FILE):
    Params.DROP = []
    Params.DROP.extend([(p.strip(), re.compile(p.strip())) for p in
        open(fpath).readlines() if p.strip() and not p.startswith('#')])

def parse_nocache(fpath=Params.NOCACHE_FILE):
    Params.NOCACHE = []
    Params.NOCACHE.extend([(p.strip(), re.compile(p.strip())) for p in
        open(fpath).readlines() if p.strip() and not p.startswith('#')])

def parse_joinlist(fpath=Params.JOIN_FILE):
    Params.JOIN = []
    if os.path.isfile(fpath):

# XXX: could put tab back into JOIN rules file
#        JOIN.extend([
#            (p.strip(), re.compile("^"+p.strip()+"$"),r.strip()) for p,r in 
#            [p2.strip().split('\t') for p2 in open(fpath).readlines() if not
#                p2.startswith('#') and p2.strip()]
#            ])
        Params.JOIN.extend([
            (
                '^'+p.split(' ')[0].strip()+'$',
                re.compile('^'+p.split(' ')[0].strip()+'$'),
                p.split(' ')[1].strip()
            ) 
            for p in
            open(fpath).readlines() 
            if p.strip() and not p.strip().startswith('#')])

def parse_rewritelist(fpath=Params.REWRITE_FILE):
    Params.REWRITE = []
    for p in open(fpath).readlines():
        if not p.strip() or p.strip().startswith('#'):
            continue
        match, replace = p.strip().split('\t')
        Params.REWRITE.append((re.compile(match), replace))

# XXX: first need to see working
def parse_rewritelist_(fpath=Params.REWRITE_FILE):
    Params.REWRITE_RULES = []
    Params.REWRITE = {}
    for p in open(fpath).readlines():
        if not p.strip() or p.strip().startswith('#'):
            continue
            
        # Parse line and cleanup, compile rule
        fields = p.strip().split('\t')
        patterns = [ re.compile(f) if f != '.*' else None for f in fields[:-1] ]

        mime_pattern, hostinfo_pattern, path_pattern, entity_match = patterns
        entity_replace = fields[-1]
      
        # Get rule number
        if entity_replace in Params.REWRITE_RULES:
            idx = Params.REWRITE_RULES.index(entity_replace)
        else:
            idx = len(Params.REWRITE_RULES)
            Params.REWRITE_RULES.append(entity_replace)

        # Store new content rewrite rules
#        REWRITE[] = 
        Params.REWRITE.append((
                mime_pattern,
                hostinfo_pattern,
                path_pattern,
                entity_mathc,
                entity_replace
            ))

def match_rewrite(mediatype, hostinfo, path):
    pass
#/XXX

def validate_joinlist(fpath=Params.JOIN_FILE):
    """
    Read all double commented lines as URLs, use on next first pattern line.
    """
    lines = [path[2:].strip() for path in open(fpath).readlines() if path.strip() and path.strip()[1]=='#']
    for path in lines:
        match = False
        for pattern, regex, repl in JOIN:
            m = regex.match(path)
            if m:
                #print 'Match', path, m.groups()
                match = True
        if not match:
            print "Error: no match for", path

class Join:

    @classmethod
    def rewrite(klass, pathref):
        if Params.JOIN:
            for pattern, regex, repl in Params.JOIN:
                m = regex.match(pathref)
                if m:
                    pathref = regex.sub(repl, pathref)
                    Params.log("Joined URL matching rule %r" % line, threshold=1)
        return pathref

class Drop:

    @classmethod
    def match(klass, path):
        for pattern, compiled in Params.DROP:
            if compiled.match(path):
                return pattern


class Rewrite:

    @classmethod
    def run(klass, chunk):
        delta = 0
        Params.log("Trying to rewrite chunk. ", 3)
        for regex, repl in Params.REWRITE:
            if regex.search(chunk):
                new_chunk, count = regex.subn(repl, chunk)
                delta += len(new_chunk)-len(chunk)
                chunk = new_chunk
            else:
                Params.log("No match on chunk", 4)
        return delta, chunk
