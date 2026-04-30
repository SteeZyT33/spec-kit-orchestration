SHELL := /usr/bin/env bash

.PHONY: install uninstall reinstall tool-install tool-reinstall help

help:
	@echo "Targets:"
	@echo "  make tool-install   # install orca from this repo via uv tool"
	@echo "  make tool-reinstall # reinstall orca from this repo via uv tool"
	@echo "  make install        # symlink canonical launcher (src/orca/assets/orca-main.sh) → ~/.local/bin/orca"
	@echo "  make uninstall      # remove ~/.local/bin/orca only if it is our managed symlink"
	@echo "  make reinstall      # refresh the canonical launcher symlink at ~/.local/bin/orca"

tool-install:
	@uv tool install --force .

tool-reinstall:
	@uv tool install --force --reinstall .

install:
	@./orca --install-self

uninstall:
	@./orca --uninstall-self

reinstall: uninstall install
