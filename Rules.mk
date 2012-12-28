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
CLN                 += $(wildcard $/*.pyc $/.coverage $/.coverage-* $/test/*.pyc $/*.log)
TEST                += test-code test-system test-protocol

# DMK += $/dynamic-makefile.mk
# DEP += $/generated-dependency

#DIR                 := $/mydir
#include                $(call rules,$(DIR)/)


$/htcache.js: $/HTCache-compile-js.hxml $/HTCache.hx 
	@haxe $(HX) $^

$/TODO.list: ./
	@GREP_F="-r -I -n --exclude *Rules.mk --exclude $@ --exclude Makefile";\
	grep $$GREP_F "FIXME" ./ > $@;\
	echo >> $@;\
	grep $$GREP_F "TODO" ./ >> $@;\
	echo >> $@;\
	grep $$GREP_F "XXX" ./ >> $@;\
	echo >> $@;\
	echo >> $@

test-code:: TESTS := 
test-code::
	@COVERAGE_PROCESS_START=.coveragerc ./unit-test $(TESTS) 2>&1 | tee unittest.log
	@\
		DATE=$$(date --rfc-3339=seconds);\
		HOST=$$(hostname -s);\
		BRANCH=$$(git status | grep On.branch | sed 's/. On branch //');\
		REV=$$(git show | grep ^commit | sed 's/commit //');\
	    PASSED=$$(grep PASSED unittest.log | wc -l);\
        ERRORS=$$(grep ERROR unittest.log | wc -l);\
		echo $$DATE, $$HOST, $$BRANCH, $$REV, unit, $$PASSED, $$ERRORS;\
        echo $$PASSED passed checks, $$ERRORS errors

# some simple test data
TEST_DATA_ENV_$d := URL_HTTP="www.w3.org/Protocols/HTTP/1.1/rfc2616bis/draft-lafon-rfc2616bis-03.txt" \
URL_CHUNKED="jigsaw.w3.org/HTTP/ChunkedScript" \
URL_FTP="ftp.debian.org:21/debian/doc/FAQ/debian-faq.en.pdf.gz"

# use 'make test-system TESTS=x' to select test number
test-system:: TEST_DATA := $(TEST_DATA_ENV_$d) 
test-system:: TESTS :=
test-system:: $/
	@COVERAGE_PROCESS_START=.coveragerc \
	   $(TEST_DATA) ./system-test $(TESTS) \
	   2>&1 | tee systemtest.log
	@\
		DATE=$$(echo $$(date --rfc-3339=seconds));\
		HOST=$$(echo $$(hostname -s));\
		BRANCH=$$(echo $$(git status | grep On.branch | sed 's/. On branch //'));\
		REV=$$(echo $$(git show | grep ^commit | sed 's/commit //'));\
		PASSED=$$(echo $$(grep PASSED systemtest.log | wc -l));\
		ERRORS=$$(echo $$(grep ERROR systemtest.log | wc -l));\
		echo $$DATE, $$HOST, $$BRANCH, $$REV, system, $$PASSED, $$ERRORS;\
		echo "$$DATE, $$HOST, $$BRANCH, $$REV, system, $$PASSED, $$ERRORS" >> test-results.tab;\
		echo $$PASSED passed checks, $$ERRORS errors

test-protocol::
	@./protocol-test 2>&1 | tee protocoltest.log
	@\
		DATE=$$(echo $$(date --rfc-3339=seconds));\
		HOST=$$(echo $$(hostname -s));\
		BRANCH=$$(echo $$(git status | grep On.branch | sed 's/. On branch //'));\
		REV=$$(echo $$(git show | grep ^commit | sed 's/commit //'));\
		PASSED=$$(echo $$(grep PASSED protocoltest.log | wc -l));\
		ERRORS=$$(echo $$(grep ERROR protocoltest.log | wc -l));\
		echo $$DATE, $$HOST, $$BRANCH, $$REV, protocol, $$PASSED, $$ERRORS;\
		echo "$$DATE, $$HOST, $$BRANCH, $$REV, protocol, $$PASSED, $$ERRORS" >> test-results.tab;\
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
