# Ghidra Pipe Server Start
#
# @category ghidra_pipe
#

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

from pipe_server import PipeServer, PythonCodeExecutor
import os

daemon = os.getenv('DAEMON', False)
if daemon == 'False':
    daemon = False
elif daemon == 'True':
    daemon = True

if __name__ == "__main__":
    PythonCodeExecutor().py_code_exec('from __main__ import *')
    gps = PipeServer(name='Ghidra Pipe Server', daemon=daemon)
    if daemon:
        gps.start()
    else:
        gps.run()
