"""
"""
import os
import re

import Params
import Runtime
from util import log



class AbstractRuleset:

    rules = []
    files = []

    main_file = None

    @classmethod
    def parse_lines(klass, fpath):
        return [ line 
                for line in 
                open(fpath).readlines() 
                if line.strip() and not line.strip().startswith('#') ]

    @classmethod
    def parse_rule(klass, line):
        "Parses first field as pattern and compiles it, returns both items. "
        pattern = '^'+line.split(' ')[0].strip()+'$'
        return (
            pattern, re.compile(pattern),
        ) 
# XXX: could put tab back into JOIN rules file, also parse continuous
# separators? Multiple spaces are a pain right now. 
#        JOIN.extend([
#            (line.strip(), re.compile("^"+line.strip()+"$"),r.strip()) for line,r in 
#            [p2.strip().split('\t') for p2 in open(fpath).readlines() if not
#                p2.startswith('#') and p2.strip()]
#            ])

    @classmethod
    def parse(klass, fpath=None):
        """
        Load new rules from file, or reload configured rules.
        """
        if not fpath:
            fpath = klass.main_file
        if fpath == klass.main_file:
            klass.rules = []
            klass.files = []
        else:
            if fpath in klass.files:
                return
        if os.path.isfile(fpath):

            klass.files.append(fpath)

            try:
                lines = klass.parse_lines(fpath)
            except Exception, e:
                log("Error parsing %s lines" % klass.__name__, Params.LOG_ERR)
                raise

            for line in lines:
                try:
                    klass.rules.append( klass.parse_rule(line) )
                except Exception, e:
                    log("Error parsing %s line: %r" % (klass.__name__, line), Params.LOG_ERR)
                    raise
            
        else:
            log("No such file: %s" % fpath, Params.LOG_ALERT)


class NoCache(AbstractRuleset):

    main_file = Params.NOCACHE_FILE

    @classmethod
    def match(klass, url):
        for pattern, compiled in klass.rules:
            p = url.find( ':' ) # find len of scheme-id
            if compiled.match( url[p+3:] ):
                return True


class Join(AbstractRuleset):

    main_file = Params.JOIN_FILE

    @classmethod
    def parse_rule(klass, line):
        "Parses two fields as match pattern and substitute pattern. "
        return (
            '^'+line.split(' ')[0].strip()+'$',
            re.compile('^'+line.split(' ')[0].strip()+'$'),
            line.split(' ')[1].strip()
        ) 

    @classmethod
    def rewrite(klass, pathref):
        """
        Rewrite a single path using loaded rules.
        """
        if klass.rules:
            for pattern, regex, repl in klass.rules:
                m = regex.match(pathref)
                if m:
                    pathref = regex.sub(repl, pathref)
                    log("Joined URL matching rule %r" % pattern,
                            threshold=Params.LOG_INFO)
        return pathref

    @classmethod
    def validate(klass):
        """
        Read all double commented lines as URL's, fail if any fails to match
        to current loaded rules.
        """
        if not klass.rules:
            log("No Rules to run", Params.LOG_WARN)
            return
        ok = True
        lines = []
        for fpath in klass.files:
            try:
                # filter test lines from join-file(s)
                lines.extend([path[2:].strip() for path in
                    open(fpath).readlines() if len(path.strip()) > 1 and
                    path.strip()[1]=='#'])
            except Exception, e:
                log("Parsing exception: %s" % e, Params.LOG_ERR)
                return
        for path in lines:
            match = False
            for pattern, regex, repl in klass.rules:
                m = regex.match(path)
                if m:
                    #print 'Match', path, m.groups()
                    match = True
            if not match:
                print "Error: no match for", path
                ok = False
        return ok

    @classmethod
    def run(klass):
        """
        (Re)run the current rules on current cache; this iterates all
        descriptors and moves and updates these whenever a (new) rule applies.
        """
        if not klass.files:
            klass.parse()
        os.chdir(Runtime.ROOT)
        for root, dirs, files in os.walk(Runtime.ROOT):
            for d in dirs:
                if d in ['.git']:
                    dirs.remove(d)
            for f in files:
                fpath = os.path.join(root, f).replace(Runtime.ROOT, '')
                fpath2 = fpath.replace(':80','')
                fpath3 = klass.rewrite(fpath2)
                assert fpath3, fpath3
                if fpath2 != fpath3:
                    log('FIXME: Renaming: %s --> %s' % (fpath2, fpath), threshold=Params.LOG_NOTE)
                    continue
                    print fpath2, fpath3
                    dirname = os.path.dirname(fpath3)
                    if dirname and not os.path.isdir(dirname):
                        print 'creating', dirname
                        os.makedirs(dirname)
                    os.rename(fpath, fpath3)


# FIXME:
class Drop(AbstractRuleset):

    main_file = Params.DROP_FILE

    @classmethod
    def match(klass, path):
        for pattern, compiled in klass.rules:
            if compiled.match(path):
                return pattern


class Rewrite(AbstractRuleset):

    main_file = Params.REWRITE_FILE

    @classmethod
    def run(klass, chunk):
        delta = 0
        log("Trying to rewrite chunk. ", 3)
        for pattern, regex, repl in klass.rules:
            if regex.search(chunk):
                new_chunk, count = regex.subn(repl, chunk)
                delta += len(new_chunk)-len(chunk)
                chunk = new_chunk
            else:
                log("No match on chunk", 4)
        return delta, chunk

    @classmethod
    def parse_rule(klass, line):
        return
# FIXME:
        fields = line.strip().split('\t')
        patterns = [ re.compile(f) if f != '.*' else None for f in fields[:-1] ]

        print len(patterns), patterns
        mime_pattern, hostinfo_pattern, path_pattern, entity_match = patterns
        entity_replace = fields[-1]

        return (
                mime_pattern,
                hostinfo_pattern,
                path_pattern,
                entity_mathc,
                entity_replace
            )


def load():
    """
    Load rules from runtime files.
    """
    for x in Drop, NoCache, Join, Rewrite:
        x.main_file = getattr(Runtime, x.__name__.upper() + "_FILE")
        x.parse()


