ROOT := $(abspath ..)
VERSION := $(shell cat $(ROOT)/VERSION)
BUILD := $(ROOT)/build
PY ?= python3

.PHONY: all clean stage stage-driver stage-companion aur-src

all: stage

clean:
	rm -rf $(BUILD)

stage:
	$(PY) $(ROOT)/packaging/stage.py all

stage-driver:
	$(PY) $(ROOT)/packaging/stage.py driver

stage-companion:
	$(PY) $(ROOT)/packaging/stage.py companion

# Produce source tarballs PKGBUILDs can point at (local file:// builds).
aur-src: stage
	mkdir -p $(BUILD)/aur
	tar -C $(BUILD)/stage-driver -czf $(BUILD)/aur/flydigi-vader4d-$(VERSION).tar.gz .
	tar -C $(BUILD)/stage-companion -czf $(BUILD)/aur/vader-companion-$(VERSION).tar.gz .
	@echo "AUR-style staged tarballs in $(BUILD)/aur/"
