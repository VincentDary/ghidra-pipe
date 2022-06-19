#!/usr/bin/env bash

################################################################################
#
# Copyright 2022 Vincent Dary
#
# This file is part of ghidra-pipe.
#
# ghidra-pipe is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# ghidra-pipe is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# ghidra-pipe. If not, see <https://www.gnu.org/licenses/>.
#
################################################################################

set -e

SCRIPT_DIR=$(cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd)

PIPE_CLIENT_TESTS="$SCRIPT_DIR/test_ghidra_pipe_client.py"


if [ "$1" == '--coverage' ];
then

    COV_DIR="./pipe_client_coverage"

    cd "$SCRIPT_DIR"
    rm -rf "$COV_DIR"
    mkdir "$COV_DIR"
    cd "$COV_DIR"

    if [[ -z "${JYTHON_BIN}" ]]; then
      JYTHON_BIN="/opt/jython/bin/coverage2"
    fi

    JYTHON_BIN=${JYTHON_BIN} PIPE_SERVER_COV=True \
    pytest --cov-report html \
           --cov="ghidra_pipe" \
           --capture=no \
           -v \
           "$PIPE_CLIENT_TESTS" \
           "${@:2}"

    cd "$SCRIPT_DIR"
    rm -rf .pytest_cache

else

    if [[ -z "${JYTHON_BIN}" ]]; then
      JYTHON_BIN="/opt/jython/bin/jython"
    fi

    JYTHON_BIN=${JYTHON_BIN} \
    pytest --capture=no \
           -v \
           "$PIPE_CLIENT_TESTS" \
           "${@}"

fi

