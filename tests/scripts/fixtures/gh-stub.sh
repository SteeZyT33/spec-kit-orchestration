#!/usr/bin/env bash
# PATH-shadow stub for `gh`. Records args to $TEST_GH_LOG; succeeds.
echo "gh $*" >> "${TEST_GH_LOG:-/dev/null}"
exit 0
