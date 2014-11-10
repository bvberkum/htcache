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
TRGT                += 
STRGT               += default dist test
CLN                 += $(wildcard $/*.pyc $/.coverage $/.coverage-* $/test/*.pyc $/*.log)
TEST                += test-code test-system 

# DMK += $/dynamic-makefile.mk
# DEP += $/generated-dependency

#DIR                 := $/mydir
#include                $(call rules,$(DIR)/)


test-code:: TESTS := 
test-code::
	@COVERAGE_PROCESS_START=.coveragerc ./unit-test $(TESTS) 2>&1 | tee unittest.log

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
#	should happen autom with COVERAGE_PROCESS_START @\
#        coverage report --omit '/usr/*';\
#        coverage html --omit '/usr/*'





#      ------------ -- 
#
-include                $(MK_SHARE)Core/Main.dirstack-pop.mk
# vim:noet:
