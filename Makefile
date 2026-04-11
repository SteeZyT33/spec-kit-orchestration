SHELL := /usr/bin/env bash

.PHONY: install uninstall reinstall tool-install tool-reinstall help

help:
	@echo "Targets:"
	@echo "  make tool-install   # install speckit-orca from this repo via uv tool"
	@echo "  make tool-reinstall # reinstall speckit-orca from this repo via uv tool"
	@echo "  make install        # symlink local wrapper into ~/.local/bin"
	@echo "  make uninstall      # remove ~/.local/bin/speckit-orca"
	@echo "  make reinstall      # reinstall local wrapper symlink"

tool-install:
	@uv tool install --force .

tool-reinstall:
	@uv tool install --force --reinstall .

install:
	@./speckit-orca --install-self

uninstall:
	@./speckit-orca --uninstall-self

reinstall: uninstall install
