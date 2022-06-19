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

from typing import Tuple, Any, Union, Iterator, List
import socket
import inspect
import sys
import os
import struct
import json
import base64
import textwrap
import contextlib
import uuid

from .pipe_default_conf import PIPE_PORT, PIPE_IP

PIPE_PORT = os.getenv('PIPE_PORT', PIPE_PORT)
PIPE_IP = os.getenv('PIPE_IP', PIPE_IP)


class TcpNetIoError(Exception):
    pass


class TcpNetIo:
    def __init__(self, sock: socket.socket):
        self.sock = sock

    def sendall(self, data: bytes):
        self.sock.sendall(data)

    def recvall(self, data_len: int) -> bytes:
        data = bytearray()
        count = 0

        while count < data_len:
            recv_bytes = self.sock.recv(min(data_len-count, 4096))
            if not recv_bytes:
                raise TcpNetIoError("socket connection broken")
            data.extend(recv_bytes)
            count += len(recv_bytes)

        return data

    def recvall_to_file(self, data_len, filename) -> int:
        count = 0

        with open(filename, 'wb') as file:
            while count < data_len:
                recv_bytes = self.sock.recv(min(data_len - count, 4096))
                if not recv_bytes:
                    raise TcpNetIoError("socket connection broken")
                file.write(recv_bytes)
                count += len(recv_bytes)

        return count

    def sendall_from_file(self, filename):
        count = 0
        data_len = os.path.getsize(filename)

        with open(filename, 'rb') as file:
            while count < data_len:
                read_bytes = file.read(min(data_len-count, 4096))
                self.sock.sendall(read_bytes)
                count += len(read_bytes)


class TcpClient:
    def __init__(self, ip_address: str, port: int):
        self.ip_address = ip_address
        self.port = port
        self.sock = None
        self.io = None

    def __enter__(self):
        self.create_connection()
        return self

    def __exit__(self, exc_type, exc_value, exc_trace):
        self.close_connection()

    def create_connection(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.io = TcpNetIo(self.sock)
        self.sock.connect((self.ip_address, self.port))

    def close_connection(self):
        self.sock.close()
        self.sock = None
        self.io = None


class JsonComEncoder(json.JSONEncoder):
    def default(self, obj: Any):
        if isinstance(obj, bytearray):
            return {'__bytearray__': True,
                    'data': base64.b64encode(obj).decode('utf-8')}
        return json.JSONEncoder.default(self, obj)


def json_com_decoder(obj: Any):
    if type(obj) == dict and '__bytearray__' in obj:
        return bytearray(base64.b64decode(obj['data']))
    return obj


class TcpJsonCom:
    def __init__(self):
        self.io = None
        self.json_bytes = None
        self.json = None

    def set_socket(self, sock: socket.socket):
        self.io = TcpNetIo(sock)

    def prepare_json(self, data: dict):
        self.json = data
        self.json_bytes = bytes(json.dumps(data, cls=JsonComEncoder), 'utf-8')

    def send_prepare(self):
        json_len = struct.pack('!I', len(self.json_bytes))
        self.io.sendall(json_len + self.json_bytes)

    def send(self, data: dict):
        self.prepare_json(data)
        self.send_prepare()

    def recv(self) -> dict:
        json_len = self.io.recvall(4)
        json_len = struct.unpack('!I', json_len)[0]
        json_bytes = self.io.recvall(json_len).decode('utf-8')
        return json.loads(json_bytes, object_hook=json_com_decoder)


class PipeFileTransferErr(Exception):
    pass


class PipeCustomComNotFound(Exception):
    pass


class PipeServerInternalErr(Exception):
    pass


class PipeServerRemoteCodeExecErr(Exception):
    def __init__(self, stacktrace, code, ip, port):
        super().__init__(stacktrace)
        self.stacktrace = stacktrace
        self.code = code
        self.ip = ip
        self.port = port
        super().__init__(stacktrace)


class PipeClientJsonRpc:
    def __init__(self, ip_address=PIPE_IP, port=PIPE_PORT):
        self.ip_address = ip_address
        self.port = port

    @staticmethod
    def _check_response_error(json_err: dict):
        if json_err['code'] == -32603:
            raise PipeServerInternalErr(json_err['data']['stacktrace'])
        elif json_err['code'] == -32000:
            raise PipeServerRemoteCodeExecErr(
                json_err['data']['stacktrace'], json_err['data']['code'],
                json_err['data']['ip'], json_err['data']['port'])

    def _rpc_request(self, method: str, args: {}) -> Union[dict, None]:
        params = dict(args)

        if 'self' in params:
            params.pop('self')

        request = {'jsonrpc': '2.0', 'id': str(uuid.uuid4()),
                   'method': method, 'params': params}

        tcp_json_com = TcpJsonCom()
        tcp_json_com.prepare_json(request)

        with TcpClient(self.ip_address, self.port) as tcp_client:
            tcp_json_com.set_socket(tcp_client.sock)
            tcp_json_com.send_prepare()

            while True:
                response = tcp_json_com.recv()
                if 'id' in response and response['id'] == request['id']:
                    if 'result' in response:
                        return response['result']
                    elif 'error' in response:
                        self._check_response_error(response['error'])
                    else:
                        return
                elif 'live_stdout' in response:
                    sys.stdout.write(response['live_stdout'])
                elif 'live_stderr' in response:
                    sys.stderr.write(response['live_stderr'])

    @staticmethod
    def _format_rpc_notification(method_name: str, params: dict):
        return {'jsonrpc': '2.0', 'method': method_name, 'params': params}

    @contextlib.contextmanager
    def _rpc_notification(self, method: str, args: {}) -> Iterator[TcpJsonCom]:
        params = dict(args)

        if 'self' in params:
            params.pop('self')

        tcp_json_com = TcpJsonCom()
        tcp_json_com.prepare_json(self._format_rpc_notification(method, params))

        with TcpClient(self.ip_address, self.port) as tcp_client:
            tcp_json_com.set_socket(tcp_client.sock)
            tcp_json_com.send_prepare()
            yield tcp_json_com

    def server_remote_shutdown(self):
        self._rpc_request('remote_shutdown', {})

    def get_server_banner(self) -> str:
        return self._rpc_request('get_server_banner', {})['banner']

    def exec(self, code: str, std_cap=False, std_forward=True
             ) -> Union[None, str]:
        return self._rpc_request('code_exec', locals())['output']

    def func_exec(self, name: str, args: Tuple, kwargs: dict, std_forward=True
                  ) -> Any:
        return self._rpc_request('func_exec', locals())['return']

    def object_proxy_new(self, class_name: str, args: Tuple, kwargs: dict,
                         std_forward=True) -> str:
        res = self._rpc_request('object_proxy_new', locals())
        return res['object_name']

    def object_proxy_getattr(self, object_name: str, name: str) -> Any:
        res = self._rpc_request('object_proxy_getattr', locals())
        return res['value'], res['type']

    def object_proxy_setattr(self, object_name: str, name: str, value: Any):
        self._rpc_request('object_proxy_setattr', locals())

    def register_custom_communicator(self, communicator_name: str, code: str):
        self._rpc_request('register_custom_communicator', locals())

    def execute_custom_communicator(self, func_name: str, com_type='binary'
                                    ) -> Union[TcpNetIo, TcpJsonCom]:
        if com_type not in ['binary', 'json']:
            raise NotImplementedError('Communication type not supported.')

        req = self._format_rpc_notification(
            self.execute_custom_communicator.__name__,
            {'communicator_name': func_name, 'com_type': com_type})
        tcp_client = TcpClient(self.ip_address, self.port)
        tcp_client.create_connection()
        tcp_json_com = TcpJsonCom()
        tcp_json_com.set_socket(tcp_client.sock)
        tcp_json_com.send(req)
        communicator_found = tcp_json_com.io.recvall(1)
        if communicator_found == b'\x00':
            if com_type == 'binary':
                return tcp_client.io
            elif com_type == 'json':
                return tcp_json_com
        else:
            raise PipeCustomComNotFound('Custom communicator not found.')

    @contextlib.contextmanager
    def _file_transfer_to_client(self, src_file: str
                                 ) -> Iterator[Tuple[TcpJsonCom, int]]:
        with self._rpc_notification('file_transfer_to_client', locals()) as (
                tcp_json_com):
            file_found = tcp_json_com.io.recvall(1)
            if file_found == b'\x00':
                file_len = struct.unpack('!Q', tcp_json_com.io.recvall(8))[0]
                yield tcp_json_com, file_len
            else:
                raise PipeFileTransferErr("File '{}' not found.".format(
                    src_file))

    @contextlib.contextmanager
    def _file_transfer_to_server(self, dst_file: str, data_len: int
                                 ) -> Iterator[Tuple[TcpJsonCom, int]]:
        with self._rpc_notification('file_transfer_to_server', locals()) as (
                tcp_json_com):
            yield tcp_json_com
            tcp_json_com.io.recvall(1)

    def file_bytes_transfer_to_client(self, src_file) -> bytes:
        with self._file_transfer_to_client(src_file) as (tcp_json_com, f_len):
            return tcp_json_com.io.recvall(f_len)

    def file_transfer_to_client(self, src_file: str, dst_file: str) -> int:
        with self._file_transfer_to_client(src_file) as (tcp_json_com, f_len):
            return tcp_json_com.io.recvall_to_file(f_len, dst_file)

    def file_bytes_transfer_to_server(self, file_bytes: bytes, dst_file: str):
        data_len = len(file_bytes)
        with self._file_transfer_to_server(dst_file, data_len) as tcp_json_com:
            tcp_json_com.io.sendall(file_bytes)

    def file_transfer_to_server(self, src_file: str, dst_file: str):
        data_len = os.path.getsize(src_file)
        with self._file_transfer_to_server(dst_file, data_len) as tcp_json_com:
            tcp_json_com.io.sendall_from_file(src_file)


class ObjProxy(object):
    def __init__(self, object_name: str, ip_address: str,
                 port: int, class_name: str, src: str = None, std_forward=True):
        self.__PROXY_IP__ = ip_address
        self.__PROXY_PORT__ = port
        self.__PROXY_OBJECT_NAME__ = object_name
        self.__PROXY_SRC__ = src
        self.__GPC__ = PipeClientJsonRpc(ip_address, port)
        self.__PROXY_CLASS_NAME__ = class_name
        self.__STD_FORWARD__ = std_forward

    def __getattr__(self, name: str) -> Any:
        v_value, v_type = self.__GPC__.object_proxy_getattr(
            self.__PROXY_OBJECT_NAME__, name)

        if v_type in ['instancemethod', 'function']:
            return self._method_factory(name)

        return v_value

    def __setattr__(self, name: str, value):
        if name in ['__GPC__', '__PROXY_CLASS_NAME__', '__PROXY_OBJECT_NAME__',
                    '__PROXY_SRC__', '__PROXY_IP__', '__PROXY_PORT__',
                    '__STD_FORWARD__ ']:
            object.__setattr__(self, name, value)
            # super(ObjProxy, self).__setattr__(name, value)
            return
        self.__GPC__.object_proxy_setattr(
            self.__PROXY_OBJECT_NAME__, name, value)

    def _method_factory(self, method_name: str) -> callable:
        def method_call(*args, **kwargs) -> Any:
            return self.__GPC__.func_exec(
                self.__PROXY_OBJECT_NAME__ + '.' + method_name, args, kwargs,
                self.__STD_FORWARD__)
        return method_call


def attach_proxy_meta(obj: Any, obj_name: str, ip_address: str, port: int,
                      src: str = None):
    setattr(obj, '__PROXY_IP__', ip_address)
    setattr(obj, '__PROXY_PORT__', port)
    setattr(obj, '__PROXY_OBJECT_NAME__', obj_name)
    setattr(obj, '__PROXY_SRC__', src)


def _class_proxy_factory(class_name: str, ip_address=PIPE_IP, port=PIPE_PORT,
                         src: str = None, std_forward=True):
    gpc = PipeClientJsonRpc(ip_address, port)

    class MetaClassProxy(type):
        def __getattr__(self, name):
            v_value, v_type = gpc.object_proxy_getattr(class_name, name)

            if v_type in ['instancemethod', 'function']:
                return self._method_factory(name)

            return v_value

        def __setattr__(self, name: str, value):
            if name in ['__PROXY_OBJECT_NAME__', '__PROXY_SRC__',
                        '__PROXY_IP__', '__PROXY_PORT__']:
                super(MetaClassProxy, self).__setattr__(name, value)
                return
            gpc.object_proxy_setattr(class_name, name, value)

        @staticmethod
        def _method_factory(name: str) -> callable:
            def method_call(*args, **kwargs) -> Any:
                return gpc.func_exec(class_name + '.' + name, args, kwargs,
                                     std_forward)
            return method_call

    class ClassProxy(metaclass=MetaClassProxy):
        def __new__(cls, *args, **kwargs):
            obj_name = gpc.object_proxy_new(class_name, args, kwargs)
            return ObjProxy(obj_name, ip_address, port, class_name, src,
                            std_forward)

    attach_proxy_meta(ClassProxy, class_name, ip_address, port, src)

    return ClassProxy


class PipeClient:
    def __init__(self, ip_address=PIPE_IP, port=PIPE_PORT, std_forward=True):
        self.ip_address = ip_address
        self.port = port
        self.std_forward = std_forward
        self.pipe_client_rpc = PipeClientJsonRpc(self.ip_address, self.port)
        # direct RPC method binding
        pcrpc = self.pipe_client_rpc
        self.get_server_banner = pcrpc.get_server_banner
        self.server_remote_shutdown = pcrpc.server_remote_shutdown
        self.file_bytes_transfer_to_client = pcrpc.file_bytes_transfer_to_client
        self.file_transfer_to_client = pcrpc.file_transfer_to_client
        self.file_bytes_transfer_to_server = pcrpc.file_bytes_transfer_to_server
        self.file_transfer_to_server = pcrpc.file_transfer_to_server

    def exec(self, code: str, std_cap=False) -> Union[None, str]:
        return self.pipe_client_rpc.exec(code, std_cap, self.std_forward)

    def obj_proxy_factory(self, object_name: str, class_name: str = None,
                          src: str = None) -> ObjProxy:
        return ObjProxy(object_name, self.ip_address, self.port, class_name,
                        src)

    def class_proxy_factory(self, class_name: str, src: str):
        return _class_proxy_factory(class_name, self.ip_address, self.port, src,
                                    self.std_forward)

    def register_class(self, class_obj: Any):
        if not inspect.isclass(class_obj):
            raise ValueError("'{}' object must be a class.".format(
                class_obj.__name__))
        src = textwrap.dedent(inspect.getsource(class_obj))
        self.pipe_client_rpc.exec(src)
        return self.class_proxy_factory(class_obj.__name__, src)

    def func_proxy_factory(self, func_name: str, src: str = None) -> callable:
        json_rpc_client = PipeClientJsonRpc(self.ip_address, self.port)

        def func_proxy(*args, **kwargs) -> Any:
            return json_rpc_client.func_exec(func_name, args, kwargs,
                                             self.std_forward)

        attach_proxy_meta(func_proxy, func_name, self.ip_address, self.port,
                          src)
        return func_proxy

    def register_func(self, func: callable,) -> callable:
        if not inspect.isfunction(func):
            raise ValueError("'{}' object must be a function.".format(
                func.__name__))
        src = textwrap.dedent(inspect.getsource(func))
        self.pipe_client_rpc.exec(src)
        return self.func_proxy_factory(func.__name__, src)

    def communicator_proxy_factory(self, func_name: str, com_type: str,
                                   src: str = None) -> callable:
        json_rpc_client = PipeClientJsonRpc(self.ip_address, self.port)

        def communicator_proxy() -> Union[TcpNetIo, TcpJsonCom]:
            return json_rpc_client.execute_custom_communicator(
                func_name, com_type)

        attach_proxy_meta(communicator_proxy, func_name, self.ip_address,
                          self.port, src)
        return communicator_proxy

    def register_custom_communicator(self, func: callable, com_type='binary'
                                     ) -> callable:
        if not inspect.isfunction(func):
            raise ValueError("'{}' must be a function.".format(func.__name__))
        src = textwrap.dedent(inspect.getsource(func))
        self.pipe_client_rpc.register_custom_communicator(func.__name__, src)
        return self.communicator_proxy_factory(func.__name__, com_type, src)
