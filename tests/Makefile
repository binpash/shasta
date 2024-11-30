.PHONY: setup_test test clean

test: rt.py ../shasta/*.py
	@find libdash_tests/tests libdash_tests/pash_tests -type f | while read f; do libdash_tests/round_trip.sh ./rt.py "$$f"; done | tee python.log
	@cat python.log | egrep '^[A-Z0-9_]+:' | cut -d ':' -f 1 | sort | uniq -c
	@grep ':' python.log && echo "FAILED" && exit 1 || exit 0

clean:
	rm -rf $(wildcard *.log) libdash_tests
