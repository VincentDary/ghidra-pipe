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

import os
import sys
import struct
import traceback
import json
import base64
import inspect
import binascii
import tempfile
import contextlib
import threading
from cStringIO import StringIO

from java.net import InetAddress, ServerSocket
from java.io import FileOutputStream, FileInputStream
from java.io import DataInputStream, DataOutputStream

import jarray

from pipe_default_conf import PIPE_IP, PIPE_PORT

PIPE_PORT = os.getenv('PIPE_PORT', PIPE_PORT)
PIPE_IP = os.getenv('PIPE_IP', PIPE_IP)


def jarray_b(bytes_seq):
    buff = jarray.zeros(0, 'b')
    buff.fromstring(bytes_seq)
    return buff


@contextlib.contextmanager
def create_temporary_empty_file():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    if os.path.exists(path) and os.path.isfile(path):
        os.remove(path)


@contextlib.contextmanager
def java_file_output_ctx(filename):
    out_fstream = FileOutputStream(filename)
    yield out_fstream
    out_fstream.close()


@contextlib.contextmanager
def java_file_input_ctx(filename):
    in_fstream = FileInputStream(filename)
    yield in_fstream
    in_fstream.close()


class JavaTcpNetIo:
    def __init__(self, java_sock):
        self.sock = java_sock
        self.in_stream = DataInputStream(self.sock.getInputStream())
        self.out_stream = DataOutputStream(self.sock.getOutputStream())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_trace):
        self.in_stream.close()
        self.out_stream.close()

    def sendall(self, jarray_byte):
        data_len = len(jarray_byte)
        self.out_stream.write(jarray_byte, 0, data_len)
        return data_len

    def recvall(self, data_len):
        recv_buff = jarray.zeros(data_len, "b")
        count = 0

        while count < data_len:
            n_read = self.in_stream.read(recv_buff, count, data_len-count)
            count += n_read

        return recv_buff

    def recvall_to_file(self, data_len, filename):
        recv_buff = jarray.zeros(4096, "b")
        count = 0

        with java_file_output_ctx(filename) as out_fstream:
            while count < data_len:
                n_read = self.in_stream.read(
                    recv_buff, 0, min(data_len-count, 4096))
                out_fstream.write(recv_buff, 0, n_read)
                count += n_read

        return count

    def sendall_from_file(self, filename):
        send_buff = jarray.zeros(4096, "b")
        data_len = os.path.getsize(filename)
        count = 0

        with java_file_input_ctx(filename) as in_fstream:
            while count < data_len:
                n_read = in_fstream.read(send_buff, 0, min(data_len-count, 4096))
                self.out_stream.write(send_buff, 0, n_read)
                count += n_read


class JarrayConvBypass:
    STUCK_LIMIT = 4096 * 8

    @classmethod
    def tostring(cls, jarray_byte):
        if len(jarray_byte) < cls.STUCK_LIMIT:
            return jarray_byte.tostring()

        with create_temporary_empty_file() as file_path:
            with java_file_output_ctx(file_path) as out_fstream:
                out_fstream.write(jarray_byte)
            with open(file_path, 'rb') as fd:
                return fd.read()

    @classmethod
    def fromstring(cls, str_bytes):
        if len(str_bytes) < cls.STUCK_LIMIT:
            return jarray_b(str_bytes)

        with create_temporary_empty_file() as tmp_file:
            with open(tmp_file, 'wb') as f:
                f.write(str_bytes)
            with java_file_input_ctx(tmp_file) as in_fstream:
                buff = jarray.zeros(len(str_bytes), 'b')
                in_fstream.read(buff)
                return buff


class JsonComEncoder(json.JSONEncoder):
    def default(self, data):
        if type(data) == bytearray:
            return {'__bytearray__': True,
                    'data': base64.b64encode(data).decode('utf-8')}
        else:
            return super(JsonComEncoder, self).default(data)


def json_com_decoder(obj):
    if type(obj) == dict and '__bytearray__' in obj:
        return bytearray(base64.b64decode(obj['data']))
    return obj


class JavaTcpJsonCom:
    def __init__(self, java_tcp_net_io):
        self.io = java_tcp_net_io

    def recv(self):
        json_len = struct.unpack('!I', self.io.recvall(4))[0]
        json_jarray_b = self.io.recvall(json_len)
        json_str = JarrayConvBypass.tostring(json_jarray_b)
        ret = json.loads(json_str, object_hook=json_com_decoder)
        return ret

    def send(self, data):
        json_str = bytes(json.dumps(data, cls=JsonComEncoder))
        json_len = struct.pack('!I', len(json_str))
        json_jarray_b = JarrayConvBypass.fromstring(json_len + json_str)
        return self.io.sendall(json_jarray_b)


class StdOutputPatch:
    def __init__(self, hook):
        self.hook = hook

    def write(self, out):
        self.hook(out)


class StdoutStderrRedirectorCtx:
    def __init__(self, stdout_write_hook=None, stderr_write_hook=None,
                 stdout_stderr_capture=False):
        self.stdout_write_hook = stdout_write_hook
        self.stderr_write_hook = stderr_write_hook
        self.stdout_stderr_capture = stdout_stderr_capture
        self.saved_stderr_stdout = None
        self.saved_stdout = sys.stdout
        self.saved_stderr = sys.stderr

    def __enter__(self):
        # required because Jython don't save stdout/err in __stdout/err__
        if self.stdout_stderr_capture:
            self.saved_stderr_stdout = StringIO()
        if self.stdout_write_hook or self.stdout_stderr_capture:
            sys.stdout = StdOutputPatch(self.stdout_write)
        if self.stderr_write_hook or self.stdout_stderr_capture:
            sys.stderr = StdOutputPatch(self.stderr_write)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout, sys.stderr = self.saved_stdout, self.saved_stderr
        self.saved_stdout = self.saved_stderr = self.saved_stderr_stdout = None

    def get_saved_stdout_stderr(self):
        if self.stdout_stderr_capture:
            return self.saved_stderr_stdout.getvalue()

    def stdout_write(self, out):
        str_out = str(out)
        if self.stdout_stderr_capture:
            self.saved_stderr_stdout.write(str_out)
        if self.stdout_write_hook:
            self.stdout_write_hook(str_out, self.saved_stdout)

    def stderr_write(self, out):
        str_out = str(out)
        if self.stdout_stderr_capture:
            self.saved_stderr_stdout.write(str_out)
        if self.stderr_write_hook:
            self.stderr_write_hook(str_out, self.saved_stderr)


class PythonCodeExecutor:
    def __init__(self):
        self.stdout_write_hook = None
        self.stderr_write_hook = None
        self.last_exc_code = None
        self.last_stacktrace = None

    def get_last_err(self):
        return {'stacktrace': self.last_stacktrace, 'code': self.last_exc_code}

    def register_stdout_stderr_write_hook(self, stdout_write_hook,
                                          stderr_write_hook):
        self.stdout_write_hook = stdout_write_hook
        self.stderr_write_hook = stderr_write_hook

    def py_code_exec(self, py_code, stdouterr_capture=False):
        with StdoutStderrRedirectorCtx(
                self.stdout_write_hook,
                self.stderr_write_hook,
                stdouterr_capture) as std:
            try:
                exec("""exec py_code in globals()""")
                stacktrace = None
            except:
                stacktrace = traceback.format_exc()
            output = std.get_saved_stdout_stderr()

        self.last_exc_code = py_code
        self.last_stacktrace = stacktrace
        return output, stacktrace

    def func_exec_wrap(self, func_name, args, kwargs):
        arg_names = []
        for i, a in enumerate(args):
            name = '__arg_{}__'.format(i)
            globals()[name] = a
            arg_names.append(name)

        kwarg_names = []
        for i, k in enumerate(kwargs):
            name = '__kwarg_{}__'.format(i)
            globals()[name] = kwargs[k]
            kwarg_names.append(name)

        code = '__ret__={}({}{}{})'.format(
            func_name, ','.join(arg_names),
            ',' if len(args) > 0 and len(kwargs) > 0 else '',
            ','.join('{}={}'.format(
                k, kwarg_names[i]) for i, k in enumerate(kwargs)))

        globals()['__ret__'] = None
        out, trace = self.py_code_exec(code)
        ret = globals()['__ret__']

        for var_name in arg_names + kwarg_names + ['__ret__']:
            globals().pop(var_name)

        return ret, out, trace


class JsonRpcServer:
    FILE_TRANSFER_FILE_FOUND = b'\x00'
    FILE_TRANSFER_FILE_NOT_FOUND = b'\xff'

    def __init__(self, ip, port, shutdown_callback):
        self.ip = ip
        self.port = port
        self._executor = PythonCodeExecutor()
        self.shutdown_callback = shutdown_callback
        self._custom_communicators = {}
        self.rpc_methods = [
            self.code_exec, self.func_exec, self.object_proxy_new,
            self.object_proxy_getattr, self.object_proxy_setattr,
            self.register_custom_communicator, self.get_server_banner,
            self.remote_shutdown]
        self.rpc_notifications = [
            self.execute_custom_communicator, self.file_transfer_to_client,
            self.file_transfer_to_server]

    @staticmethod
    def stdout_stderr_hooks(json_com, std_client_forward):
        def _stdout_write_hook(out, stdout):
            if std_client_forward:
                json_com.send({'live_stdout': out})
            else:
                stdout.write(out)

        def _stderr_write_hook(err, stderr):
            if std_client_forward:
                json_com.send({'live_stderr': err})
            else:
                stderr.write(err)

        return _stdout_write_hook, _stderr_write_hook

    def _response_error(self, uid, code,  message, data=None):
        response = {'jsonrpc': '2.0', 'id': uid,
                    'error': {'code': code, 'message': message,
                              'data': {'ip': self.ip, 'port': self.port}}}
        if data:
            response['error']['data'].update(data)
        return response

    @staticmethod
    def _response(request_id, result=None):
        response = {'jsonrpc': '2.0', 'id': request_id}
        if result:
            response.update({'result': result})
        return response

    def dispatcher(self, tcp_net_io):
        json_com = JavaTcpJsonCom(tcp_net_io)
        data = json_com.recv()

        if 'id' in data:  # RPC request
            try:
                for method in self.rpc_methods:
                    if method.__name__ == data['method']:
                        method(json_com, data['id'], data['params'])
            except Exception as ex:
                dat = {'stacktrace': traceback.format_exc()}
                json_com.send(self._response_error(data['id'], -32603, '', dat))
                raise ex
        else:  # RPC notification
            for method in self.rpc_notifications:
                if method.__name__ == data['method']:
                    method(json_com, data['params'])

    def get_server_banner(self, json_com, uid, args):
        json_com.send(self._response(uid, {'banner': 'PipeServer JSON RPC v2'}))

    def code_exec(self, json_com, uid, args):
        self._executor.register_stdout_stderr_write_hook(
            *self.stdout_stderr_hooks(json_com, args['std_forward']))
        out, trace = self._executor.py_code_exec(args['code'], args['std_cap'])

        if trace:
            data = self._executor.get_last_err()
            json_com.send(self._response_error(uid, -32000, '', data))
        else:
            json_com.send(self._response(uid, {'output': out}))

    def func_exec(self, json_com, uid, args):
        self._executor.register_stdout_stderr_write_hook(
            *self.stdout_stderr_hooks(json_com, args['std_forward']))
        ret, _, trace = self._executor.func_exec_wrap(
            args['name'], args['args'], args['kwargs'])

        if trace:
            data = self._executor.get_last_err()
            json_com.send(self._response_error(uid, -32000, '', data))
        else:
            json_com.send(self._response(uid, {'return': ret}))

    def object_proxy_new(self, json_com, uid, args):
        self._executor.register_stdout_stderr_write_hook(
            *self.stdout_stderr_hooks(json_com, args['std_forward']))
        ret, _, trace = self._executor.func_exec_wrap(
            args['class_name'], args['args'], args['kwargs'])

        if trace:
            data = self._executor.get_last_err()
            json_com.send(self._response_error(uid, -32000, '', data))
        else:
            name = args['class_name'] + '_' + binascii.b2a_hex(os.urandom(5))
            globals()[name] = ret
            json_com.send(self._response(uid, {'object_name': name}))

    def object_proxy_getattr(self, json_com, uid, args):
        value = getattr(globals()[args['object_name']], args['name'])
        value_type = type(value).__name__
        if value_type in ['instancemethod', 'function']:
            value = str(value)

        msg = self._response(uid, {'type': value_type, 'value': value})
        json_com.send(msg)

    def object_proxy_setattr(self, json_com, uid, args):
        setattr(globals()[args['object_name']], args['name'], args['value'])
        json_com.send(self._response(uid))

    def remote_shutdown(self, json_com, uid, args):
        self.shutdown_callback()
        json_com.send(self._response(uid))

    def register_custom_communicator(self, json_com, uid, args):
        _, trace = self._executor.py_code_exec(args['code'])

        if trace:
            data = self._executor.get_last_err()
            json_com.send(self._response_error(uid, -32000, '', data))
        else:
            comm_func = globals()[args['communicator_name']]
            self._custom_communicators.update(
                {args['communicator_name']: comm_func})
            json_com.send(self._response(uid))

    def execute_custom_communicator(self, json_com, args):
        if args['communicator_name'] in self._custom_communicators:
            json_com.io.sendall(jarray_b(b'\x00'))
            if args['com_type'] == 'binary':
                self._custom_communicators[args['communicator_name']](
                    json_com.io)
            elif args['com_type'] == 'json':
                self._custom_communicators[args['communicator_name']](json_com)
        else:
            json_com.io.sendall(jarray_b(b'\xff'))

    def file_transfer_to_client(self, json_com, args):
        if os.path.exists(args['src_file']) and os.path.isfile(args['src_file']):
            file_len = struct.pack('!Q', os.path.getsize(args['src_file']))
            json_com.io.sendall(jarray_b(self.FILE_TRANSFER_FILE_FOUND))
            json_com.io.sendall(jarray_b(file_len))
            json_com.io.sendall_from_file(args['src_file'])
        else:
            json_com.io.sendall(jarray_b(self.FILE_TRANSFER_FILE_NOT_FOUND))

    @staticmethod
    def file_transfer_to_server(json_com, args):
        json_com.io.recvall_to_file(args['data_len'], args['dst_file'])
        json_com.io.sendall(jarray_b(b'\xff'))


class PipeServer(threading.Thread):
    def __init__(self, ip_address=PIPE_IP, port=PIPE_PORT, name='',
                 daemon=False):
        threading.Thread.__init__(self)
        self.daemon = daemon
        self.name = name
        self.port = port
        self.ip_address = ip_address
        self.sock = None
        self.is_running = False

    def remote_shutdown(self):
        if self.is_running:
            self.is_running = False
            self.sock.close()
            self.sock = None
            print('[i] {} stop'.format(self.name))

    def run(self):
        inet_addr = InetAddress.getByName(self.ip_address)
        self.sock = ServerSocket(self.port, 1, inet_addr)
        self.sock.setReuseAddress(True)
        self.is_running = True
        print('[i] {} start'.format(self.name))
        json_rpc_server = JsonRpcServer(
            self.ip_address, self.port, self.remote_shutdown)

        while self.is_running:
            client_sock = self.sock.accept()

            try:
                with JavaTcpNetIo(client_sock) as client_tcp_net_io:
                    json_rpc_server.dispatcher(client_tcp_net_io)
            except:
                print(traceback.format_exc())
            finally:
                client_sock.close()
