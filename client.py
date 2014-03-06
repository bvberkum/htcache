#!/usr/bin/env python
import urllib2


def main(args):

	cmd = 'list'
	if args:
		cmd = args.pop()
	fl = urllib2.urlopen('http://dandy.local:8081/%s' % cmd)
	print fl.read()


if __name__ == '__main__':
	import sys
	main(sys.argv[1:]);
