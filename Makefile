PACK:=htcache
VERSION:=0.1
REV:=$(shell cat REVISION)
SRC:=$(PACK) init.sh $(wildcard *.py) $(wildcard *.rst) \
	filtered-placeholder.html \
	forbidden-sign.png forbidden-sign.svg

.PHONY: default dist
default:

TODO.list: ./
	rgrep -I -n --exclude Makefile "XXX\|FIXME\|TODO" ./ > $@

snapshot:
	echo $$(expr $$(cat REVISION) + 1) > REVISION
	tar czvf dist/$(PACK)_$(VERSION)_r$$(cat REVISION).tar.gz $(SRC)

dist:
	tar czvf dist/$(PACK)_$(VERSION).tar.gz $(SRC)


# :vim:set noet:
