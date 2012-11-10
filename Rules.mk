-include                $(MK_SHARE)Core/Main.dirstack.mk
MK_$d               := $/Rules.mk
MK                  += $(MK_$d)
#
#      ------------ -- 


PACK_$d             := htcache
VERSION_$d          := 0.4
# XXX: REV_$d              := $(shell cat REVISION)
#SNAPSHOT_$d := dist/$(PACK_$d)_$(VERSION_$d)_$$.tar.gz
DIST_$d             := $/dist/$(PACK)_$(VERSION).tar.gz 

SRC                 += init.sh $(wildcard *.py) $(wildcard *.rst) \
	filtered-placeholder.html \
	forbidden-sign.png forbidden-sign.svg \
	HTCache.hx
TRGT                += $/TODO.list $/htcache.js
STRGT               += default dist test
CLN                 += $(wildcard $/*.pyc $/.coverage $/.coverage-*)
TEST                += test-code test-protocol

# DMK += $/dynamic-makefile.mk
# DEP += $/generated-dependency

#DIR                 := $/mydir
#include                $(call rules,$(DIR)/)


$/htcache.js: $/HTCache-compile-js.hxml $/HTCache.hx 
	@haxe $(HX) $^

$/TODO.list: ./
	@rgrep -I -n --exclude Makefile "XXX\|FIXME\|TODO" ./ > $@

test-code:: TESTS := 
test-code::
	@COVERAGE_PROCESS_START=.coveragerc ./unit-test $(TESTS) 2>&1 | tee utest.log
	@echo $$(grep PASSED utest.log | wc -l) passed checks, $$(grep ERROR utest.log | wc -l) errors

test-protocol::
	@./system-test 2>&1 | tee systest.log
	@echo $$(grep PASSED systest.log | wc -l) passed checks, $$(grep ERROR systest.log | wc -l) errors


debug::
	-mkdir debug-root
	htcache -v -v -r debug-root -f debug-root/resources.db

#$(SNAPSHOT_$d):
#	echo $$(expr $$(cat REVISION) + 1) > REVISION
#	tar czvf $(SNAPSHOT_$d) $(SRC)

dist::
	tar czvf $(DIST_$d) $(SRC)



#      ------------ -- 
#
-include                $(MK_SHARE)Core/Main.dirstack-pop.mk
# vim:noet:
