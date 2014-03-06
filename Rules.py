"""
"""
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
#		REWRITE[] = 
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


class Join:

	rules = []
	files = []

	@classmethod
	def rewrite(klass, pathref):
		if klass.rules:
			for pattern, regex, repl in klass.rules:
				m = regex.match(pathref)
				if m:
					pathref = regex.sub(repl, pathref)
					Params.log("Joined URL matching rule %r" % pattern, threshold=1)
		return pathref

	@classmethod
	def parse(klass, fpath=None):
		if not fpath:
			fpath = Params.JOIN_FILE
		if fpath != Params.JOIN_FILE:
			klass.rules = []
			klass.files = []
		else:
			if fpath in klass.files:
				return
		if os.path.isfile(fpath):
			klass.files.append(fpath)
# XXX: could put tab back into JOIN rules file
#		JOIN.extend([
#			(p.strip(), re.compile("^"+p.strip()+"$"),r.strip()) for p,r in 
#			[p2.strip().split('\t') for p2 in open(fpath).readlines() if not
#				p2.startswith('#') and p2.strip()]
#			])
			klass.rules.extend([
				(
					'^'+p.split(' ')[0].strip()+'$',
					re.compile('^'+p.split(' ')[0].strip()+'$'),
					p.split(' ')[1].strip()
				) 
				for p in
				open(fpath).readlines() 
				if p.strip() and not p.strip().startswith('#')])
		else:
			Params.log("No such file: %s" % fpath, Params.LOG_ALERT)

	@classmethod
	def validate(klass):
		"""
		Read all double commented lines as URLs, use on next first pattern line.
		"""
		if not klass.rules:
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
				Params.log("Parsing exception: %s" % e, Params.LOG_ERR)
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
