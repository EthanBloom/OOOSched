.PHONY: clean test

test: DynamicSched.py test.in
	env python3 OOPDynamicSched.py test.in > out.txt

clean:
	-rm out.txt
