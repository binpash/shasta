.PHONY: setup_test test clean

test: rt.py ../shasta/*.py libdash_tests setup_test
	@find libdash_tests/tests libdash_tests/pash_tests -type f | while read f; do libdash_tests/round_trip.sh ./rt.py "$$f"; done | tee python.log
	@cat python.log | egrep '^[A-Z0-9_]+:' | cut -d ':' -f 1 | sort | uniq -c
	@grep ':' python.log && echo "FAILED" && exit 1 || exit 0

libdash_tests:
	git clone https://github.com/binpash/libdash.git
	mv libdash/test libdash_tests
	rm -rf libdash

setup_test:
	pip install .. libdash

clean:
	rm -rf $(wildcard *.log) libdash_tests
