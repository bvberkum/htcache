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
		TOTAL=$$(grep '^Ran..*tests.in' unittest.log | sed 's/Ran.\([0-9]\+\).tests.*$$/\1/');\
		[ -z "$$TOTAL" ] && TOTAL=0;\
		LOGTAIL=$$(tail -1 unittest.log);\
		if echo $$LOGTAIL | grep -q errors;then\
		ERRORS=$$(echo $$(echo $$LOGTAIL | sed 's/.*errors\=\([0-9]\+\).*/\1/'));\
	    else ERRORS=0;fi;\
		if echo $$LOGTAIL | grep -q failures;then\
		FAILURES=$$(echo $$(echo $$LOGTAIL | sed 's/.*failures\=\([0-9]\+\).*/\1/'));\
        else FAILURES=0; fi;\
		echo $$TOTAL - $$ERRORS - $$FAILURES;\
		PASSED=$$(( $$TOTAL - $$ERRORS - $$FAILURES ));\
		echo $$DATE, $$HOST, $$BRANCH, $$REV, unit, $$PASSED, $$ERRORS, $$FAILURES;\
		echo "$$DATE, $$HOST, $$BRANCH, $$REV, unit, $$PASSED, $$ERRORS, $$FAILURES" >> test-results.tab;\
		echo "$$PASSED passed checks, $$ERRORS errors, $$FAILURES failures ($$TOTAL total)"

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

test-protocol::
	@echo "[ TEST ] Starting proxy for protocol tests..."
	@-rm -rf /tmp/htcache-test-protocol.cache/
	@mkdir /tmp/htcache-test-protocol.cache/
	@-rm -rf /tmp/htcache-test-protocol.data/
	@mkdir /tmp/htcache-test-protocol.data/
	@./htcache --daemon /tmp/htcache-test-protocol.log \
		-p 8081 -r /tmp/htcache-test-protocol.cache/ \
		--data-dir /tmp/htcache-test-protocol.data/ \
		--pid-file /tmp/htcache-test-protocol.pid \
		--log-level 0 \
	;
	@echo "[ TEST ] Started proxy, running tests..."
	@./protocol-test 2>&1 | tee protocoltest.log
	@kill -int `cat /tmp/htcache-test-protocol.pid`
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
	mkdir -p debug-root
	[ -e "debug-root/resources.db" ] || { sqlite3 debug-root/resources.db; }
	./htcache --log-level 1 -r debug-root --data sqlite:///debug-root/resources.db

#$(SNAPSHOT_$d):
#	echo $$(expr $$(cat REVISION) + 1) > REVISION
#	tar czvf $(SNAPSHOT_$d) $(SRC)

dist::
	tar czvf $(DIST_$d) $(SRC)



#      ------------ -- 
#
-include                $(MK_SHARE)Core/Main.dirstack-pop.mk
# vim:noet:
