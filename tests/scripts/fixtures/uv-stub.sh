#!/usr/bin/env bash
# PATH-shadow stub for `uv`. Records args; succeeds.
echo "uv $*" >> "${TEST_UV_LOG:-/dev/null}"
exit 0
