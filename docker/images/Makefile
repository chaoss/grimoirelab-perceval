PERCEVAL_VERSION = master
.PHONY: help
help:
	$(info )
	$(info This makefile will help you build docker images for Perceval)
	$(info )
	$(info Available options:)
	$(info )
	$(info - all:			Build all available images)
	$(info - perceval:	Build Perceval branch Master)
	$(info )
	@echo ""

.PHONY: perceval
perceval:
	docker build -t grimoirelab/perceval:$(PERCEVAL_VERSION) $(PERCEVAL_VERSION)/

.PHONY: all
all: perceval
