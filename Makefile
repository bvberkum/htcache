PACK:=htcache
VERSION:=0.1
REV:=$(shell cat REVISION)
SRC:=$(PACK) init.sh $(wildcard *.py) $(wildcard *.rst) \
	filtered-placeholder.html \
	forbidden-sign.png forbidden-sign.svg

.PHONY: default dist

default:

test::
	@COVERAGE_PROCESS_START=.coveragerc ./unit-test | tee /tmp/htcache-make.log
	@echo $$(grep PASSED /tmp/htcache-make.log | wc -l) passed checks, $$(grep ERROR /tmp/htcache-make.log | wc -l) errors

clean::
	@find ./ \
	    -name '*.pyc' \
	    -exec rm -rvf {} +
	@find ./ \
	    -name '.coverage' \
	    -exec rm -rvf {} +
	@find ./ \
	    -name '.coverage-*' \
	    -exec rm -rvf {} +

debug::
	-mkdir debug-root
	htcache -v -v -r debug-root -f debug-root/resources.db

TODO.list: ./
	rgrep -I -n --exclude Makefile "XXX\|FIXME\|TODO" ./ > $@

snapshot::
	echo $$(expr $$(cat REVISION) + 1) > REVISION
	tar czvf dist/$(PACK)_$(VERSION)_r$$(cat REVISION).tar.gz $(SRC)

dist::
	tar czvf dist/$(PACK)_$(VERSION).tar.gz $(SRC)


# :vim:set noet:
