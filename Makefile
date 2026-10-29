ARCH ?= x86_64
.PHONY: check image visual evidence clean
check:
	./scripts/check.sh
image:
	./scripts/build-image.sh $(ARCH)
visual:
	./scripts/boot-test.sh $(ARCH)
evidence:
	./scripts/package-evidence.sh
clean:
	rm -rf build dist evidence
