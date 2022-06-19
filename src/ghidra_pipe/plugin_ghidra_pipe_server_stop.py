# Ghidra-Pipe Server Remote Shutdown
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

import uuid

from java.net import Socket

from pipe_default_conf import PIPE_IP, PIPE_PORT
from pipe_server import JavaTcpNetIo, JavaTcpJsonCom

if __name__ == "__main__":
    try:
        java_socket = Socket(PIPE_IP, PIPE_PORT)
        with JavaTcpNetIo(java_socket) as tcp_net_io:
            json_com = JavaTcpJsonCom(tcp_net_io)
            req = {'jsonrpc': '2.0', 'id': str(uuid.uuid4()),
                   'method': 'remote_shutdown', 'params': {}}
            json_com.send(req)
            json_com.recv()
        java_socket.close()
    except:
        pass
