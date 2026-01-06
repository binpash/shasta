.PHONY: test dash_test bash_test gosh_test clean

dash_test:
	@find libdash_tests/tests libdash_tests/pash_tests -type f | while read f; do libdash_tests/round_trip.sh ./rt.py "$$f"; done | tee python.log
	@cat python.log | egrep '^[A-Z0-9_]+:' | cut -d ':' -f 1 | sort | uniq -c
	@grep ':' python.log && echo "FAILED" && exit 1 || exit 0

bash_test:
	@./bash_tests/test.py # returns 1 on failure

gosh_test:
	@find libdash_tests/tests libdash_tests/pash_tests -type f | while read f; do libdash_tests/round_trip.sh ./gosh_rt.py "$$f"; done | tee -a python.log
	@find bash_tests/test_files -type f | while read f; do libdash_tests/round_trip.sh ./gosh_rt.py "$$f"; done | tee -a python.log
	@cat python.log | egrep '^[A-Z0-9_]+:' | cut -d ':' -f 1 | sort | uniq -c
	@grep ':' python.log && echo "FAILED" && exit 1 || exit 0

test: dash_test bash_test gosh_test

clean:
	rm -rf $(wildcard *.log) libdash_tests
