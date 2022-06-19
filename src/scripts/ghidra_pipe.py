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

import sys
import os
import shutil


def ghidra_plugin_install(target_path):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    file_list = [
        'pipe_server.py',
        'pipe_default_conf.py',
        'plugin_ghidra_pipe_server_start.py',
        'plugin_ghidra_pipe_server_stop.py'
    ]
    sanitized_target_path = os.path.normpath(target_path)
    full_target_path = os.path.join(sanitized_target_path, 'ghidra-pipe')

    os.mkdir(os.path.normpath(full_target_path))
    for filename in file_list:
        src = os.path.join(script_dir, '..', 'ghidra_pipe', filename)
        dst = os.path.join(full_target_path, filename)
        shutil.copy(src, dst)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--plugin-install':
        ghidra_plugin_install(sys.argv[2])
