default:

TODO.list: ./
	rgrep -I -n --exclude Makefile "XXX\|FIXME\|TODO" ./ > $@

# :vim:set not:
