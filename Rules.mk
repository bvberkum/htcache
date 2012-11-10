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
	@\
		DATE=$$(date --rfc-3339=seconds);\
		HOST=$$(hostname -s);\
		BRANCH=$$(git status | grep On.branch | sed 's/. On branch //');\
		REV=$$(git show | grep ^commit | sed 's/commit //');\
	    PASSED=$$(grep PASSED utest.log | wc -l);\
        ERRORS=$$(grep ERROR utest.log | wc -l);\
		echo $$DATE, $$HOST, $$BRANCH, $$REV, unit, $$PASSED, $$ERRORS;\
		echo "$$DATE, $$HOST, $$BRANCH, $$REV, unit, $$PASSED, $$ERRORS" >> test-results.tab;\
        echo $$PASSED passed checks, $$ERRORS errors

test-protocol::
	@./system-test 2>&1 | tee systest.log
	@\
		DATE=$$(echo $$(date --rfc-3339=seconds));\
		HOST=$$(echo $$(hostname -s));\
		BRANCH=$$(echo $$(git status | grep On.branch | sed 's/. On branch //'));\
		REV=$$(echo $$(git show | grep ^commit | sed 's/commit //'));\
		PASSED=$$(echo $$(grep PASSED systest.log | wc -l));\
		ERRORS=$$(echo $$(grep ERROR systest.log | wc -l));\
		echo $$DATE, $$HOST, $$BRANCH, $$REV, system, $$PASSED, $$ERRORS;\
		echo "$$DATE, $$HOST, $$BRANCH, $$REV, system, $$PASSED, $$ERRORS" >> test-results.tab;\
		echo $$PASSED passed checks, $$ERRORS errors

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
