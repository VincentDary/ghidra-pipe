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

import pytest
import subprocess
import os
import signal
import psutil
import time
import sys
import hashlib
import shutil
import contextlib
import tempfile

from ghidra_pipe import PipeClient

from ghidra_pipe import TcpNetIoError
from ghidra_pipe import PipeServerRemoteCodeExecErr
from ghidra_pipe import PipeServerInternalErr
from ghidra_pipe import PipeFileTransferErr

from ghidra_pipe import PipeClientJsonRpc
from ghidra_pipe import PipeCustomComNotFound


JYTHON_BIN = os.getenv('JYTHON_BIN', 'jython')
PIPE_SERVER_COV = os.getenv('PIPE_SERVER_COV', None)

TEST_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PIPE_SERVER_START_SCRIPT = os.path.join(
    TEST_SCRIPT_DIR, '..', 'src', 'ghidra_pipe',
    'plugin_ghidra_pipe_server_start.py')


def kill_ghidra_pipe_server():
    for proc in psutil.process_iter():
        try:
            if sys.platform == 'linux':
                if PIPE_SERVER_START_SCRIPT in proc.cmdline():
                    os.kill(proc.pid, signal.SIGKILL)
                    print('[i] Pipe server killed')
            elif sys.platform == 'win32':
                if (proc.name() in ['jython', 'jython.exe', 'coverage2',
                                    'coverage2.exe']
                        and PIPE_SERVER_START_SCRIPT in proc.cmdline()):
                    subprocess.call(
                        ['taskkill', '/F', '/T', '/PID', str(proc.pid)])
                    print('[i] Pipe server killed')
        except (psutil.PermissionError, psutil.AccessDenied):
            pass


def setup_module(module):
    kill_ghidra_pipe_server()

    if PIPE_SERVER_COV:
        pipe_server_cov_dir = os.path.join(
            TEST_SCRIPT_DIR, 'pipe_server_coverage')

        if os.path.exists(pipe_server_cov_dir) \
                and os.path.isdir(pipe_server_cov_dir):
            shutil.rmtree(pipe_server_cov_dir)
        os.mkdir(pipe_server_cov_dir)

        popen_args = ['run', PIPE_SERVER_START_SCRIPT]
        popen_cwd = pipe_server_cov_dir
    else:
        popen_cwd = None
        popen_args = [PIPE_SERVER_START_SCRIPT]

    env = dict(os.environ)
    env.update({'DAEMON': 'False'})
    subprocess.Popen([JYTHON_BIN, *popen_args], cwd=popen_cwd, env=env)

    pipe_client = PipeClient()
    while True:
        try:
            banner = pipe_client.get_server_banner()
            if banner:
                break
        except (ConnectionRefusedError, ConnectionResetError):
            time.sleep(2)


################################################################################
# Test PipeFileTransferClient
################################################################################


@contextlib.contextmanager
def temp_bin_file():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    yield path
    if os.path.exists(path) and os.path.isfile(path):
        os.remove(path)


def test_file_bytes_transfer_to_server():
    with temp_bin_file() as tmp_file:
        content = os.urandom(int(4096 * 2.5))
        content_hash = hashlib.sha1(content).hexdigest()
        PipeClient().file_bytes_transfer_to_server(content, tmp_file)
        with open(tmp_file, 'rb') as remote_fd:
            assert hashlib.sha1(remote_fd.read()).hexdigest() == content_hash


def test_file_transfer_to_server():
    with temp_bin_file() as local_file, temp_bin_file() as remote_file:
        content = os.urandom(int(4096 * 10.5))
        content_hash = hashlib.sha1(content).hexdigest()
        with open(local_file, 'wb') as f:
            f.write(content)
        PipeClient().file_transfer_to_server(local_file, remote_file)
        with open(remote_file, 'rb') as f:
            assert hashlib.sha1(f.read()).hexdigest() == content_hash


def test_file_bytes_transfer_to_client():
    with temp_bin_file() as remote_file:
        content = os.urandom(int(4096 * 2.5))
        content_hash = hashlib.sha1(content).hexdigest()
        with open(remote_file, 'wb') as f:
            f.write(content)
        local_cont = PipeClient().file_bytes_transfer_to_client(remote_file)
        assert hashlib.sha1(local_cont).hexdigest() == content_hash
        assert len(local_cont) == int(4096 * 2.5)


def test_file_transfer_to_client():
    with temp_bin_file() as remote_file,  temp_bin_file() as local_file:
        content = os.urandom(int(4096 * 10.5))
        content_hash = hashlib.sha1(content).hexdigest()
        with open(remote_file, 'wb') as f:
            f.write(content)
        count = PipeClient().file_transfer_to_client(remote_file, local_file)
        with open(local_file, 'rb') as f:
            assert hashlib.sha1(f.read()).hexdigest() == content_hash
            assert count == int(4096 * 10.5)


def test_file_bytes_transfer_to_client_file_not_exit():
    tempf = tempfile.NamedTemporaryFile()
    tempf.close()

    with pytest.raises(PipeFileTransferErr):
        PipeClient().file_bytes_transfer_to_client(tempf.name)


def test_file_transfer_to_client_file_not_exit():
    tempf_1 = tempfile.NamedTemporaryFile()
    tempf_2 = tempfile.NamedTemporaryFile()
    tempf_1.close()
    tempf_2.close()

    with pytest.raises(PipeFileTransferErr):
        PipeClient().file_transfer_to_client(tempf_1.name, tempf_2.name)


################################################################################
# Test pipe_register_func
################################################################################


def test_pipe_register_func_type_int():
    def type_int(x):
        return 2 + x
    type_int = PipeClient().register_func(type_int)
    assert type_int(3) == 5


def test_pipe_register_func_type_float():
    def type_float(x):
        return float(0.25+x)
    type_float = PipeClient().register_func(type_float)
    assert type_float(0.05) == 0.3


def test_pipe_register_func_type_bool():
    def negate_bool(x):
        return not x
    negate_bool = PipeClient().register_func(negate_bool)
    assert not negate_bool(True)
    assert negate_bool(False)


def test_pipe_register_func_type_str():
    def type_str(x):
        return 'B' + x
    type_str = PipeClient().register_func(type_str)
    assert type_str('A') == 'BA'


def test_pipe_register_func_type_none():
    def type_none(x):
        return x
    type_none = PipeClient().register_func(type_none)
    assert not type_none(None)


def test_pipe_register_func_type_dict():
    def type_dict(x):
        ret_dict = {'B': 7}
        ret_dict.update(x)
        return ret_dict
    type_dict = PipeClient().register_func(type_dict)
    assert type_dict({'A': 6}) == {'A': 6, 'B': 7}


def test_pipe_register_func_type_list():
    def type_list(x):
        return [69] + x
    type_list = PipeClient().register_func(type_list)
    assert type_list(['EE']) == [69, 'EE']


def test_pipe_register_func_type_bytearray():
    def type_bytearray(x):
        return bytearray(b'\xde\xad') + x
    type_bytearray = PipeClient().register_func(type_bytearray)
    assert type_bytearray(bytearray(b'\xbe')) == bytearray(b'\xde\xad\xbe')


def test_pipe_register_func_args():
    def func_args(arg_1, arg_2, arg_3):
        return arg_1, arg_2, arg_3

    func_args = PipeClient().register_func(func_args)
    ret_1, ret_2, ret_3 = func_args(9, 'A', {'F': 5})
    assert ret_1 == 9
    assert ret_2 == 'A'
    assert ret_3 == {'F': 5}


def test_pipe_register_func_kargs():
    def func_kargs(karg1=9, karg2='A', karg3=True):
        return karg1, karg2, karg3

    func_kargs = PipeClient().register_func(func_kargs)
    ret_1, ret_2, ret_3 = func_kargs()
    assert ret_1 == 9
    assert ret_2 == 'A'
    assert ret_3

    ret_1, ret_2, ret_3 = func_kargs(7, 'B', False)
    assert ret_1 == 7
    assert ret_2 == 'B'
    assert not ret_3

    ret_1, ret_2, ret_3 = func_kargs(karg3=False, karg1=7, karg2='B')
    assert ret_1 == 7
    assert ret_2 == 'B'
    assert not ret_3


def test_pipe_register_func_args_kwargs():
    def func_args_kargs(arg1, arg2, arg3, karg1=9, karg2='A', karg3=True):
        return arg1, arg2, arg3, karg1, karg2, karg3

    func_args_kargs = PipeClient().register_func(func_args_kargs)
    ret_1, ret_2, ret_3, ret_4, ret_5, ret_6 = func_args_kargs(
        9, 'A', False, karg3=True, karg1=7, karg2='B')

    assert ret_1 == 9
    assert ret_2 == 'A'
    assert not ret_3
    assert ret_4 == 7
    assert ret_5 == 'B'
    assert ret_6


def test_pipe_register_func_big_args_size_len():
    def func_big_arg(x):
        return x

    func_big_arg = PipeClient().register_func(func_big_arg)
    big_len = 4096 * 11
    big_args = bytearray(big_len * b'\xff')
    ret = func_big_arg(big_args)
    assert len(ret) == big_len


def test_pipe_register_func_raise_exception():
    def raise_exception():
        raise ValueError('Test Exception Value Error')

    raise_exception = PipeClient().register_func(raise_exception)

    with pytest.raises(PipeServerRemoteCodeExecErr) as exc_info:
        raise_exception()

    assert 'ValueError: Test Exception Value Error' in str(exc_info)


def test_pipe_register_func_client_send_unsupported_type():
    def client_send_unsupported_type(x):
        return x

    client_send_unsupported_type = PipeClient().register_func(
        client_send_unsupported_type)

    class UnsupportedType:
        pass

    with pytest.raises(TypeError):
        client_send_unsupported_type(UnsupportedType())


def test_pipe_register_func_server_send_unsupported_type():
    def server_send_unsupported_type():
        class UnsupportedType:
            pass
        return UnsupportedType

    server_send_unsupported_type = PipeClient().register_func(
        server_send_unsupported_type)

    with pytest.raises(PipeServerInternalErr) as exc_info:
        server_send_unsupported_type()

    assert 'is not JSON serializable' in str(exc_info)


def test_pipe_register_func_invalid_code():
    def invalid_code():
        return not_exist

    invalid_code = PipeClient().register_func(invalid_code)

    with pytest.raises(PipeServerRemoteCodeExecErr) as exc_info:
        invalid_code()

    assert "NameError: global name \\'not_exist\\' is not defined" \
           in str(exc_info)


def test_pipe_register_func_write_stdout(capsys):
    def print_aa():
        print('Aa')

    print_aa = PipeClient().register_func(print_aa)
    print_aa()
    captured = capsys.readouterr()
    assert captured.out == 'Aa\n'


def test_pipe_client_function_no_std_forward(capsys):
    def print_bb():
        print('bb')

    pipe_client = PipeClient(std_forward=False)
    print_bb = pipe_client.register_func(print_bb)
    print_bb()
    captured = capsys.readouterr()
    assert captured.out == ''


def test_pipe_register_func_use_remote_global_scope():
    def a1():
        globals()['CCC'] = 45

    def a2():
        return CCC

    a1 = PipeClient().register_func(a1)
    a2 = PipeClient().register_func(a2)

    a1()
    assert a2() == 45


def test_pipe_register_func_invalid_decoration():
    class InvalidFunction:
        pass

    with pytest.raises(ValueError):
        PipeClient().register_func(InvalidFunction)

################################################################################
# Test pipe_register_class
################################################################################


def test_pipe_register_class_proxy_unicity():
    class FooClassA:
        CLASS_ATTR_A = 'CLASS_ATTR_A'

    class FooClassB:
        CLASS_ATTR_B = 'CLASS_ATTR_B'

    FooClassA = PipeClient().register_class(FooClassA)
    FooClassB = PipeClient().register_class(FooClassB)

    assert FooClassA.CLASS_ATTR_A == 'CLASS_ATTR_A'
    assert FooClassB.CLASS_ATTR_B == 'CLASS_ATTR_B'
    assert FooClassA.__PROXY_OBJECT_NAME__ == 'FooClassA'
    assert FooClassB.__PROXY_OBJECT_NAME__ == 'FooClassB'


def test_pipe_register_class_call_static_method():
    class StaticMethod:
        @staticmethod
        def bar(x):
            return x

    StaticMethod = PipeClient().register_class(StaticMethod)
    assert StaticMethod.bar('a str') == 'a str'


def test_pipe_register_class_call_class_method():
    class ClassMethod:
        CLASS_ATTR = 55

        @classmethod
        def bar(cls, x):
            return cls.CLASS_ATTR + x

    ClassMethod = PipeClient().register_class(ClassMethod)
    assert ClassMethod.bar(5) == 60


def test_pipe_register_class_set_class_attribute():
    class SetClassAttr:
        CLASS_ATTR = 55
    SetClassAttr = PipeClient().register_class(SetClassAttr)
    SetClassAttr.CLASS_ATTR = 65
    assert SetClassAttr.CLASS_ATTR == 65


def test_pipe_register_class_type_int():
    class TypeInt:
        def type_int(self, x):
            return 2 + x
    TypeInt = PipeClient().register_class(TypeInt)
    assert TypeInt().type_int(3) == 5


def test_pipe_register_class_type_float():
    class TypeFloat:
        def type_float(self, x):
            return float(0.25+x)
    TypeFloat = PipeClient().register_class(TypeFloat)
    assert TypeFloat().type_float(0.05) == 0.3


def test_pipe_register_class_type_bool():
    class TypeBool:
        def negate_bool(self, x):
            return not x
    TypeBool = PipeClient().register_class(TypeBool)
    assert not TypeBool().negate_bool(True)
    assert TypeBool().negate_bool(False)


def test_pipe_register_class_type_str():
    class TypeStr:
        def type_str(self, x):
            return 'B' + x
    TypeStr = PipeClient().register_class(TypeStr)
    assert TypeStr().type_str('A') == 'BA'


def test_pipe_register_class_type_none():
    class TypeNone:
        def type_none(self, x):
            return x
    TypeNone = PipeClient().register_class(TypeNone)
    assert not TypeNone().type_none(None)


def test_pipe_register_class_type_dict():
    class TypeDict:
        def type_dict(self, x):
            ret_dict = {'B': 7}
            ret_dict.update(x)
            return ret_dict
    TypeDict = PipeClient().register_class(TypeDict)
    assert TypeDict().type_dict({'A': 6}) == {'A': 6, 'B': 7}


def test_pipe_register_class_type_list():
    class TypeList:
        def type_list(self, x):
            return [69] + x
    TypeList = PipeClient().register_class(TypeList)
    assert TypeList().type_list(['EE']) == [69, 'EE']


def test_pipe_register_class_type_bytearray():
    class TypeByteArray:
        def type_bytearray(self, x):
            return bytearray(b'\xde\xad') + x
    TypeByteArray = PipeClient().register_class(TypeByteArray)
    assert TypeByteArray().type_bytearray(bytearray(b'\xbe')) == \
           bytearray(b'\xde\xad\xbe')


def test_pipe_register_class_args():
    class ListArgs:
        def method_args(self, arg1, arg2, arg3):
            return arg1, arg2, arg3

    ListArgs = PipeClient().register_class(ListArgs)
    ret_1, ret_2, ret_3 = ListArgs().method_args(9, 'A', {'F': 5})
    assert ret_1 == 9
    assert ret_2 == 'A'
    assert ret_3 == {'F': 5}


def test_pipe_register_class_kargs():
    class DictKwarg:
        def method_kargs(self, karg1=9, karg2='A', karg3=True):
            return karg1, karg2, karg3

    DictKwarg = PipeClient().register_class(DictKwarg)

    ret_1, ret_2, ret_3 = DictKwarg().method_kargs()
    assert ret_1 == 9
    assert ret_2 == 'A'
    assert ret_3

    ret_1, ret_2, ret_3 = DictKwarg().method_kargs(7, 'B', False)
    assert ret_1 == 7
    assert ret_2 == 'B'
    assert not ret_3

    ret_1, ret_2, ret_3 = DictKwarg().method_kargs(
        karg3=False, karg1=7, karg2='B')
    assert ret_1 == 7
    assert ret_2 == 'B'
    assert not ret_3


def test_pipe_register_class_args_kwargs():
    class ArgsKwargs:
        def method_args_kargs(self, arg1, arg2, arg3, karg1=9, karg2='A',
                              karg3=True):
            return arg1, arg2, arg3, karg1, karg2, karg3

    ArgsKwargs = PipeClient().register_class(ArgsKwargs)

    ret_1, ret_2, ret_3, ret_4, ret_5, ret_6 = ArgsKwargs().method_args_kargs(
        9, 'A', {'F': 5}, karg3=False, karg1=7, karg2='B')

    assert ret_1 == 9
    assert ret_2 == 'A'
    assert ret_3 == {'F': 5}
    assert ret_4 == 7
    assert ret_5 == 'B'
    assert not ret_6


def test_pipe_register_class_raise_exception():
    class Raiser:
        def raise_exception(self):
            raise ValueError('Test Exception Value Error')

    Raiser = PipeClient().register_class(Raiser)
    raiser_instance = Raiser()

    with pytest.raises(PipeServerRemoteCodeExecErr) as exc_info:
        raiser_instance.raise_exception()

    assert 'ValueError: Test Exception Value Error' in str(exc_info)


def test_pipe_register_class_client_send_unsupported_type():
    class ClientNoTypeSupport:
        def client_send_unsupported_type(self, x):
            return x

    class UnsupportedType:
        pass

    ClientNoTypeSupport = PipeClient().register_class(ClientNoTypeSupport)

    with pytest.raises(TypeError):
        ClientNoTypeSupport().client_send_unsupported_type(UnsupportedType())


def test_pipe_register_class_server_send_unsupported_type():
    class ServerNoTypeSupport:
        def server_send_unsupported_type(self):
            class UnsupportedType:
                pass
            return UnsupportedType

    ServerNoTypeSupport = PipeClient().register_class(ServerNoTypeSupport)

    with pytest.raises(PipeServerInternalErr) as exc_info:
        ServerNoTypeSupport().server_send_unsupported_type()

    assert 'is not JSON serializable' in str(exc_info)


def test_pipe_register_class_invalid_code():
    class InvalidCode:
        def invalid_code(self):
            return not_exist

    InvalidCode = PipeClient().register_class(InvalidCode)

    with pytest.raises(PipeServerRemoteCodeExecErr) as exc_info:
        InvalidCode().invalid_code()

    assert "NameError: global name \\'not_exist\\' is not defined" in \
           str(exc_info)


def test_pipe_register_class_attr_direct_access():
    class ClassAttrAccess:
        CLASS_ATTR = 60

    ClassAttrAccess = PipeClient().register_class(ClassAttrAccess)
    assert ClassAttrAccess().CLASS_ATTR == 60


def test_pipe_register_class_attr_direct_set():
    class ClassAttrSet:
        CLASS_ATTR = 60

    ClassAttrSet = PipeClient().register_class(ClassAttrSet)
    foo = ClassAttrSet()
    foo.CLASS_ATTR = 70
    assert foo.CLASS_ATTR == 70


def test_pipe_register_class_attr_method_access():
    class ClassAttrMetAccess:
        CLASS_ATTR = 60

        @classmethod
        def classmethod_class_attr_access(cls):
            return cls.CLASS_ATTR

        def method_class_attr_access(self):
            return self.CLASS_ATTR

    ClassAttrMetAccess = PipeClient().register_class(ClassAttrMetAccess)
    assert ClassAttrMetAccess().classmethod_class_attr_access() == 60
    assert ClassAttrMetAccess().method_class_attr_access() == 60


def test_pipe_register_class_attr_method_set():
    class ClassAttrUsage:
        CLASS_ATTR = 60

        @classmethod
        def classmethod_class_attr_set(cls, x):
            cls.CLASS_ATTR = x

        def method_class_attr_set(self, x):
            self.CLASS_ATTR = x

        @classmethod
        def classmethod_class_attr_access(cls):
            return cls.CLASS_ATTR

        def method_class_attr_access(self):
            return self.CLASS_ATTR

    ClassAttrUsage = PipeClient().register_class(ClassAttrUsage)
    foo = ClassAttrUsage()
    foo.classmethod_class_attr_set(70)
    assert foo.classmethod_class_attr_access() == 70
    foo.method_class_attr_set(80)
    assert foo.method_class_attr_access() == 80


def test_pipe_register_class_instance_attr_not_exist():
    class AttrNotExist:
        pass

    AttrNotExist = PipeClient().register_class(AttrNotExist)

    with pytest.raises(PipeServerInternalErr):
        x = AttrNotExist().x


def test_pipe_register_class_instance_method_not_exist():
    class MethodNoExist:
        pass

    MethodNoExist = PipeClient().register_class(MethodNoExist)

    with pytest.raises(PipeServerInternalErr):
        MethodNoExist().x()


def test_pipe_register_class_instance_attr_direct_access():
    class InstanceAttrAccess:
        def __init__(self):
            self.x = 70
    InstanceAttrAccess = PipeClient().register_class(InstanceAttrAccess)
    assert InstanceAttrAccess().x == 70


def test_pipe_register_class_instance_attr_method_access():
    class InstanceAttrViaMethod:
        def __init__(self):
            self.x = 70

        def get_x(self):
            return self.x

    InstanceAttrViaMethod = PipeClient().register_class(InstanceAttrViaMethod)
    assert InstanceAttrViaMethod().get_x() == 70


def test_pipe_register_class_instance_attr_direct_set():
    class InstanceAttrSet:
        def __init__(self):
            self.x = 70

    InstanceAttrSet = PipeClient().register_class(InstanceAttrSet)
    foo = InstanceAttrSet()
    foo.x = 90
    assert foo.x == 90


def test_pipe_register_class_instance_attr_method_set():
    class InstanceAttrMetSet:
        def __init__(self):
            self.x = 70

        def set_x(self, v):
            self.x = v

    InstanceAttrMetSet = PipeClient().register_class(InstanceAttrMetSet)
    foo = InstanceAttrMetSet()
    foo.set_x(100)
    assert foo.x == 100


def test_pipe_register_class_instance_write_stdout(capsys):
    class WriteStdout:
        def print_aa(self):
            print('Bb')

    WriteStdout = PipeClient().register_class(WriteStdout)
    WriteStdout().print_aa()
    captured = capsys.readouterr()
    assert captured.out == 'Bb\n'


def test_pipe_client_class_method_no_std_forward(capsys):
    class ClassMethodNoStd:
        @staticmethod
        def stdout_write(a):
            sys.stdout.write(a)

    pipe_client = PipeClient(std_forward=False)
    ClassMethodNoStd = pipe_client.register_class(ClassMethodNoStd)
    ClassMethodNoStd.stdout_write("from stdout")
    captured = capsys.readouterr()
    assert captured.out == ''


def test_pipe_client_instance_method_no_std_forward(capsys):
    class InstanceMethodNoStd:
        @staticmethod
        def stdout_write(a):
            sys.stdout.write(a)

    pipe_client = PipeClient(std_forward=False)
    InstanceMethodNoStd = pipe_client.register_class(InstanceMethodNoStd)
    InstanceMethodNoStd().stdout_write("from stdout")
    captured = capsys.readouterr()
    assert captured.out == ''


def test_pipe_register_class_invalid_decoration():
    def invalid_class():
        pass

    with pytest.raises(ValueError):
        PipeClient().register_class(invalid_class)


################################################################################
# Test Exec
################################################################################

def test_pipe_client_exec_with_stdout(capsys):
    pipe_client = PipeClient()
    out = pipe_client.exec('sys.stdout.write("from stdout")', std_cap=True)
    captured = capsys.readouterr()
    assert captured.out == 'from stdout'
    assert out == 'from stdout'


def test_pipe_client_exec_with_stderr(capsys):
    pipe_client = PipeClient()
    out = pipe_client.exec('sys.stderr.write("from stderr")', std_cap=True)
    captured = capsys.readouterr()
    assert captured.err == 'from stderr'
    assert out == 'from stderr'


def test_pipe_client_exec_no_std_forward(capsys):
    pipe_client = PipeClient(std_forward=False)
    out = pipe_client.exec('sys.stdout.write("from stdout")', std_cap=True)
    captured = capsys.readouterr()
    assert captured.out == ''
    assert out == 'from stdout'
    err = pipe_client.exec('sys.stderr.write("from stderr")', std_cap=True)
    captured = capsys.readouterr()
    assert captured.err == ''
    assert err == 'from stderr'


def test_pipe_client_exec_raise_code_exec_error():
    pipe_client = PipeClient()
    with pytest.raises(PipeServerRemoteCodeExecErr):
        pipe_client.exec('z = ')

################################################################################
# Test pipe_register_custom_communicator
################################################################################


def test_register_custom_communicator_by_decorator():
    def test_communicator(tcp_net_io):
        client_msg = tcp_net_io.recvall(4)
        tcp_net_io.sendall(client_msg)
        buff = jarray.zeros(0, 'b')
        buff.fromstring(b'\xDE\xAD\xC0\xDE')
        tcp_net_io.sendall(buff)

    test_communicator = PipeClient().register_custom_communicator(
        test_communicator)
    echo_msg = b'\xC0\xDE\xC0\xFE'
    client_tcp_io = test_communicator()
    client_tcp_io.sendall(echo_msg)
    server_echo_msg = client_tcp_io.recvall(4)
    good_by_msg = client_tcp_io.recvall(4)
    assert server_echo_msg == echo_msg
    assert good_by_msg == b'\xDE\xAD\xC0\xDE'


def test_register_custom_communicator_json_com():
    def json_coffee_communicator(tcp_json_com):
        tcp_json_com.send({'data': 'C0DEC0FE'})
        while True:
            msg_in = tcp_json_com.recv()
            if msg_in['data'] == 'C0FEBAB1':
                tcp_json_com.send({'data': 'DEADBEEF'})
                tcp_json_com.io.sock.close()
            else:
                tcp_json_com.send({'data': 'retry'})

    json_coffee_communicator = PipeClient().register_custom_communicator(
        json_coffee_communicator, com_type='json')

    client_tcp_json_com = json_coffee_communicator()
    assert client_tcp_json_com.recv() == {'data': 'C0DEC0FE'}
    client_tcp_json_com.send({'data': 'C0FEBAB1'})
    assert client_tcp_json_com.recv() == {'data': 'DEADBEEF'}


def test_register_custom_communicator_invalid_com_type():
    def custom_communicator_invalid_com_type(tcp_xml_com):
        pass

    custom_communicator_invalid_com_type = \
        PipeClient().register_custom_communicator(
            custom_communicator_invalid_com_type, com_type='xml')

    with pytest.raises(NotImplementedError):
        custom_communicator_invalid_com_type()


def test_register_custom_communicator_recv_broken_pipe():
    def test_communicator_recv_broken_pipe(tcp_net_io):
        buff = jarray.zeros(0, 'b')
        buff.fromstring(b'\xDE\xAD\xBE\xEF')
        tcp_net_io.sendall(buff)
        tcp_net_io.sock.close()

    test_communicator_recv_broken_pipe = \
        PipeClient().register_custom_communicator(
            test_communicator_recv_broken_pipe)

    with pytest.raises(TcpNetIoError):
        client_tcp_io = test_communicator_recv_broken_pipe()
        client_tcp_io.recvall(5)


def test_register_custom_communicator_recv_to_file_broken_pipe():
    def test_communicator_recv_to_file_broken_pipe(tcp_net_io):
        buff = jarray.zeros(0, 'b')
        buff.fromstring(b'\xDE\xAD\xBE\xEF')
        tcp_net_io.sendall(buff)
        tcp_net_io.sock.close()

    test_communicator_recv_to_file_broken_pipe = \
        PipeClient().register_custom_communicator(
            test_communicator_recv_to_file_broken_pipe)

    with temp_bin_file() as temp_file:
        with pytest.raises(TcpNetIoError):
            client_tcp_io = test_communicator_recv_to_file_broken_pipe()
            client_tcp_io.recvall_to_file(5, temp_file)


def test_register_custom_communicator_invalid_decoration():
    class InvalidCommunicator:
        def __init__(self, tcp_net_io):
            pass

    with pytest.raises(ValueError):
        PipeClient().register_custom_communicator(InvalidCommunicator)


def test_register_custom_communicator_not_found():
    client_json_rpc = PipeClientJsonRpc()
    with pytest.raises(PipeCustomComNotFound):
        client_json_rpc.execute_custom_communicator(
            'this_communicator_not_exist')


################################################################################
# Test Object Proxy
################################################################################

def test_object_proxy():
    class TestObjecProxy:
        def foo(self):
            return 100

    pipe_client = PipeClient()
    TestObjecProxy = pipe_client.register_class(TestObjecProxy)
    test_object_proxy_inst = TestObjecProxy()

    proxy = pipe_client.obj_proxy_factory(
        test_object_proxy_inst.__PROXY_OBJECT_NAME__)

    assert proxy.foo() == 100

################################################################################
# Test remote shutdown
################################################################################

@pytest.mark.order(index=-1)
def test_pipe_server_remote_shutdown():
    PipeClient().server_remote_shutdown()
