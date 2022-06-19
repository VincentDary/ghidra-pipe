# Ghidra Pipe: Teleport Python code from CPython to Jython



* [What is Ghidra Pipe](#what-is-ghidra-pipe)
* [Installation](#installation)
* [Start/Stop the Pipe Server](#startstop-the-pipe-server)
* [Setting Custom port and hostname for the Pipe](#setting-custom-port-and-hostname-for-the-pipe)
  + [Server Side](#server-side)
  + [Client Side](#client-side)
* [Teleport Python Code from CPython 3 to Jython](#teleport-python-code-from-cpython-3-to-jython)
  + [Code](#code)
  + [Function](#function)
  + [Class](#class)
  + [Standard Output and Error Redirection](#standard-output-and-error-redirection)
  + [Remote Exception](#remote-exception)
  + [Full Usage Example](#full-usage-example)
* [Custom Pipe Communication Routines](#custom-pipe-communication-routines)
  + [Custom Binary Communication Example](#custom-binary-communication-example)
  + [Custom JSON Communication Example](#custom-json-communication-example)
* [Reach Existing Remote Object from Everywhere Through Proxy](#reach-existing-remote-object-from-everywhere-through-proxy)
* [Proxy Remote Object Tracking Information](#proxy-remote-object-tracking-information)
* [File Copy Through Pipe](#file-copy-through-pipe)
* [Pipe Server JSON RPC Interface](#pipe-server-json-rpc-interface)
* [Development](#development)
* [FAQ](#faq)
  + [Why an Another Tool](#why-an-another-tool)
  + [Why the Pipe Server use Java Socket](#why-the-pipe-server-use-java-socket)
  + [Why Ghidra-Pipe no Proxify Ghidra API in the Client Side Global Namespace](#why-ghidra-pipe-no-proxify-ghidra-api-in-the-client-side-global-namespace)
 
 

## What is Ghidra Pipe

Ghidra-Pipe provides various ways to interface custom reverse engineering tools with Ghidra environment and its Ghidra Jython API. On one side, a Ghidra Python script run a pipe server which exposes several services though RPC methods. On the other hand, Ghidra-Pipe provides a pipe client API to access these services. The pipe client and the server communicate through classic TCP socket with the JSON RPC V2 protocol. So it is possible to implement a custom pipe client in any language to use the pipe server services. The network traffic is non encrypted (on local by default), since this tool is for research purpose no effort have been done for encrypted communication.

Summary of features:

- Teleport Python code from CPython 3 to Jython:
  * Remote Python code execution;
  * Remote Python functions declaration;
  * Remote Python class declaration;
  * Function call, class usage and object creation/usage through proxy.
- Custom pipe communication:
  * Remote custom communication routine declaration;
  * Custom communication channel opening through proxy;
  * Helpers for binary/JSON communication.
- File copy from local to remote or from remote to local.
- JSON RPC V2 interface:
  * Python code execution;
  * Python function execution; 
  * Python object creation;
  * Python object attribute getter and setter;
  * Register/call custom Python communicator;
  * File copy from local to remote or from remote to local.
- Lightweight code (< 1000 loc), zero dependency and easy to modify to feet your need.


## Installation

Install the Ghidra-Pipe Python package from the Python Package Index (PyPI).

```text
$ pip install ghidra-pipe
```

Copy the pipe server plugins to a custom Ghidra plugins directory.  

```text
$ ghidra-pipe --plugin-install /path/to/ghidra_plugins
```

The plugin installer copy the following Python script in the ghidra-pipe directory.

```text
$ tree ghidra-pipe/
ghidra-pipe/
├── pipe_default_conf.py
├── pipe_server.py
├── plugin_ghidra_pipe_server_start.py
└── plugin_ghidra_pipe_server_stop.py

0 directories, 4 files
```


This tool has been tested on these platforms and configuration, but can probably work on variant.

| OS          | Python | Jython | Java Runtime                      |
|-------------|--------|--------|-----------------------------------|
| GNU/linux   | 3.10.5 | 2.7.2  | OpenJDK 11.0.15+10                |
| GNU/linux   | 3.8.0  | 2.7.2  | OpenJDK 11.0.15+10                |
| GNU/linux   | 3.7.0  | 2.7.2  | OpenJDK 11.0.15+10                |
| GNU/linux   | 3.6.0  | 2.7.2  | OpenJDK 11.0.15+10                |
| GNU/linux   | 3.5.4  | 2.7.2  | OpenJDK 11.0.15+10                |
| Windows x64 | 3.10.5 | 2.7.2  | adoptopenjdk jdk-17.0.3.7-hotspot |
| Windows x64 | 3.8.1  | 2.7.2  | adoptopenjdk jdk-17.0.3.7-hotspot |
| Windows x64 | 3.7.1  | 2.7.2  | adoptopenjdk jdk-17.0.3.7-hotspot |
| Windows x64 | 3.6.0  | 2.7.2  | adoptopenjdk jdk-17.0.3.7-hotspot |
| Windows x64 | 3.5.3  | 2.7.2  | adoptopenjdk jdk-17.0.3.7-hotspot |

## Start/Stop the Pipe Server

Start the pipe server via the Ghidra GUI, open the script manager window in `Window > Script Manager`, and  run  the  script `plugin_ghidra_pipe_server_start.py` localised in the `ghidra_pipe` directory.

Stop the pipe server via the Ghidra GUI, open the script manager window in `Window > Script Manager`, and  run  the  script `plugin_ghidra_pipe_server_stop.py` localised in the `ghidra_pipe` directory.

It is also possible to stop the pipe server via the pipe client API.

```text
>>> from ghidra_pipe import PipeClient
>>> PipeClient().server_remote_shutdown()
```

## Setting Custom port and hostname for the Pipe

### Server Side

By default, the pipe server listen for incoming connection on localhost and TCP port 5098. These parameters are configurable through the configuration file localised in the Ghidra-Pipe plugins directory in `ghidra_pipe/pipe_default_conf.py` with the variables `PIPE_IP` and `PIPE_PORT` (before Python module import).

### Client Side

By default, all pipe client methods initiate connection on localhost and TCP port 5098. These parameters are configurable globally via the environment variables `PIPE_IP` and `PIPE_PORT` (before Python module import). Otherwise, the `PipeClient` class accept the optional keyword arguments `ip_address` and `port`.

```text
>>> from ghidra_pipe import PipeClient
>>> pipe_client = PipeClient(ip_address='192.168.1.35', port=5090)
```

## Teleport Python Code from CPython 3 to Jython

Teleport Python code from CPython 3 to Jython requires that the teleported code is compatible with CPython 3 and the remote version of Jython (2/3).

### Code

The `PipeClient.exec` method allows for remote Python code execution. The method take Python source code as argument which will be executed on the remote global namespace of the pipe server via a classic exec. Note that this Python source code does not need to be compatible Python 3 since it will be never evaluate locally. Stdout and stderr of the code executed remotely is forwarded locally and can be captured and returned by the method if the `std_cap` option is set.

```text
>>> from ghidra_pipe import PipeClient
>>> pipe_client = PipeClient()
>>> pipe_client.exec("""
... import sys
... print(sys.version)
... """)
2.7.2 (v2.7.2:925a3cc3b49d, Mar 21 2020, 10:03:58)
[OpenJDK 64-Bit Server VM (Oracle Corporation)]
```

Since the code is executed in the remote global namespace of the pipe server all your import and object created at runtime are available between `exec` call.

```text
>>> pipe_client.exec('a = 78')
>>> output = pipe_client.exec('print(a)', std_cap=True)
78
>>> output
'78\n'
```

This feature can be useful to execute a third party script in Jython interpreter. 

```text
>>> with open('/tmp/test_jython_script.py', 'r') as f:
...     output = PipeClient().exec(f.read(), std_cap=True)
... 
```


### Function

The `PipeClient.register_func` method allow remote function declaration. It retrieves the source code of the function pass as argument and execute it on the remote global namespace of the pipe server. Note that this feature is supported natively in IPython REPL but not in classic REPL due to source code retrieving issues.  

```python
from ghidra_pipe import PipeClient

def remote_func(a, b=True):
    return a, b

remote_func = PipeClient().register_func(remote_func)
```

The method return a function proxy which can be used to invoke the remote Python function transparently. Function arguments and return values are limited to the following Python basic types : None, int, float, bool, str, dict, list, tuple, bytearray. Stdout and stderr of the function invoked remotely is forwarded locally.

```python
print(remote_func)
a, b = remote_func(4, b=False)
print(a)
print(b)
```

Output.

```text
<function PipeClient.func_proxy_factory.<locals>.func_proxy at 0x7f1b249abac0>
4
False
```



### Class

The `PipeClient.register_class` method allow remote class declaration. It retrieves the source code of the class pass as argument and execute it on the remote global namespace of the pipe server. Note that this feature is not supported in Python/IPython REPL due to source code retrieving issues.  

```python
from ghidra_pipe import PipeClient

class Foo:
    CLASS_ATTR = 78

    @staticmethod
    def static_method(a):
        return a

    @classmethod
    def class_method(cls):
        return cls.CLASS_ATTR + 2

    def instance_method(self):
        print(self)

Foo = PipeClient().register_class(Foo)
```

The decorator return a class proxy which can be used transparently as a standalone class or to create new object.

```python
print(Foo)
print(Foo.CLASS_ATTR)
print(Foo.static_method(5))
print(Foo.class_method())
```

Output.
```text
<class 'ghidra_pipe.pipe_client._class_proxy_factory.<locals>.ClassProxy'>
78
5
80
```

When the class proxy is called for new object creation, a new object is created in the remote global namespace of the pipe server and the class proxy return an object proxy which can be used transparently.


```python
foo_obj =  Foo()
print(foo_obj)
foo_obj.instance_method()
```

Output.
```text
<ghidra_pipe.pipe_client.ObjProxy object at 0x7febb567b070>
<pipe_server.Foo instance at 0x80>
```


Note that attributes access, return values, class and object method arguments are limited to the following Python basic types : None, int, float, bool, str, dict, list, bytearray. Stdout and stderr of the class/object methods executed remotely is forwarded locally.

### Standard Output and Error Redirection

By default, the standard output and the standard error of the code executed remotely are forwarded to the standard output and error of the client. This behaviour can be change with the `std_forward` flag of the `PipeClient`.

```text
>>> from ghidra_pipe import PipeClient
>>> PipeClient().exec('print("debug")')
debug
>>> PipeClient(std_forward=False).exec('print("debug")')
```


### Remote Exception

If Python code executed remotely raise an exception an `PipeServerRemoteCodeExecErr` exception is raised locally. This exception contains various debug information as the code which raise the exception, the remote stacktrace, the port and the ip of the pipe server.


```python
from ghidra_pipe import PipeClient, PipeServerRemoteCodeExecErr

def this_func_raise_an_exception():
    v = 1 + not_exist

this_func_raise_an_exception = PipeClient().register_func(this_func_raise_an_exception)

try:
    this_func_raise_an_exception()
except PipeServerRemoteCodeExecErr as ex:
    print(ex.code)
    print('-'*10)
    print(ex.stacktrace)
    print('-'*10)
    print(ex.ip)
    print(ex.port)
```

Output.
```text
__ret__=this_func_raise_an_exception()
----------
Traceback (most recent call last):
  File "/home/pink/ghidra-pipe/src/ghidra_pipe/pipe_server.py", line 263, in py_code_exec
    exec("""exec py_code in globals()""")
  File "<string>", line 1, in <module>
  File "<string>", line 1, in <module>
  File "<string>", line 2, in this_func_raise_an_exception
NameError: global name 'not_exist' is not defined

----------
localhost
5098
```

### Full Usage Example

This demonstration script shows how the pipe client interface can be used in a complementary way. First, the `PipeClient.exec` is used to perform Python module import in the remote global namespace of the pipe server. Next, The class `GhidraColor` and the functions `set_memory_color`, `get_current_addr` are declared in the remote global namespace though the `PipeClient.register_class` and the `PipeClient.register_func` methods. Then these class and functions are used locally to color 8 bytes of memory in blue and the next 8 bytes of memory in white. Next, the `PipeClient.exec` send code to the pipe server which use these same class and functions remotely to color the next 8 bytes of memory in blue.

```python
from ghidra_pipe import PipeClient

pipe_client = PipeClient()

# Python modules import
pipe_client.exec("""
from ghidra.program.model.address import AddressSet
from ghidra.app.plugin.core.colorizer import ColorizingService
from java.awt import Color
""")
    
class GhidraColor:
    def __init__(self):
        self.colorizing_service = state.getTool().getService(ColorizingService)

    def set_color(self, addr, rgb1, rgb2, rgb3):
        self.colorizing_service.setBackgroundColor(
            toAddr(addr), toAddr(addr), Color(rgb1, rgb2, rgb3))

def set_memory_color(addr, rgb1, rgb2, rgb3):
    # Usage of class GhidraColor previously declared
    g_color = GhidraColor()
    g_color.set_color(addr, rgb1, rgb2, rgb3)

def get_current_addr():
    return int(currentAddress.toString(), 16)

# Remote object declaration
GhidraColor = pipe_client.register_class(GhidraColor)
set_memory_color = pipe_client.register_func(set_memory_color)
get_current_addr = pipe_client.register_func(get_current_addr)

# Local usage of remote class and function declared
current_addr = get_current_addr()
ghidra_color = GhidraColor()
ghidra_color.set_color(current_addr, 0, 0, 255)  # blue
ghidra_color.set_color(current_addr + 4, 0, 0, 255)  # blue
set_memory_color(current_addr + 8, 255, 255, 255)  # white
set_memory_color(current_addr + 12, 255, 255, 255)  # white

# Remote usage of class and function declared remotly
pipe_client.exec("""
current_addr = get_current_addr()
remote_ghidra_color = GhidraColor()
remote_ghidra_color.set_color(current_addr + 16, 255, 0, 0)  # red
remote_ghidra_color.set_color(current_addr + 20, 255, 0, 0)  # red
""")
```


## Custom Pipe Communication Routines

The `PipeClient.register_custom_communicator` method allows to create a custom communication channels between an external tools and the remote routine. It retrieves the source code of the function pass as argument and executes it on the remote global namespace of the pipe server. The remote function is registered as a custom communication routine and become available. A communicator proxy is returned which can be used to open a custom communication channel with the remote routine. The code of the routine must compatible with CPython 3 and the remote version of Jython (2/3)Python.

### Custom Binary Communication Example

The following example registers the `coffee_communicator` communication routine. The routine send the value `0xc0dec0fe` to the client and enter an infinite receive loop which except the value `0xc0febab1` to close the communication. 

```python
from ghidra_pipe import PipeClient

def coffee_communicator(tcp_net_io):
  msg_out = jarray.zeros(0, 'b')
  msg_out.fromstring(b'\xC0\xDE\xC0\xFE')
  tcp_net_io.sendall(msg_out)
  while True:
    msg_in = tcp_net_io.recvall(4)
    msg_out = jarray.zeros(0, 'b')
    if msg_in.tostring() == b'\xC0\xFE\xBA\xB1':
      msg_out.fromstring(b'\xDE\xAD\xBE\xEF')
      tcp_net_io.sendall(msg_out)
      tcp_net_io.sock.close()
      return
    else:
      msg_out.fromstring(b'\xFF\xFF\xFF\xFF')
      tcp_net_io.sendall(msg_out)

coffee_communicator = PipeClient().register_custom_communicator(coffee_communicator)
print(coffee_communicator)
```
Output.
```
<function PipeClient.communicator_proxy_factory.<locals>.communicator_proxy at 0x7fc858293880>
```

When the communicator proxy is invoked a communication channel is open with the pipe server and the remote communication routine on the server side is called with a `pipe_server.JavaTcpNetIo` instance as argument. The communicator proxy return a `pipe_client.TcpNetIo` instance. These two objects in each side wrap a client socket connected to each other and provide communication helper methods (`sendall`, `recvall`, `recvall_to_file`, `sendall_from_file`)

```python
client_tcp_net_io = coffee_communicator()
print(client_tcp_net_io)
print(client_tcp_net_io.sock)
```
Output.
```text
<ghidra_pipe.pipe_client.TcpNetIo object at 0x7fc858392320>
<socket.socket fd=3, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('127.0.0.1', 60350), raddr=('127.0.0.1', 5098)>
```

Next the communication with the remote routine is easy.

```python
print( client_tcp_net_io.recvall(4) )
client_tcp_net_io.sendall(b'\xC0\xFE\xBA\xB1')
print( client_tcp_net_io.recvall(4) )
```
Output.
```text
bytearray(b'\xc0\xde\xc0\xfe')
bytearray(b'\xde\xad\xbe\xef')
```

Use the underlying socket to close the communication.

```python
client_tcp_net_io.sock.close()
```


### Custom JSON Communication Example

The following example registers the `json_coffe_communicator` communication routine. The routine send a JSON message with the string 'C0DEC0FE' to the client and enter an infinite receive loop which except a JSON message with the string 'C0FEBAB1' to close the communication. 

```python
from ghidra_pipe import PipeClient

def json_coffee_communicator(tcp_json_com):
    tcp_json_com.send({'data': 'C0DEC0FE' })
    while True:
        msg_in = tcp_json_com.recv()
        if msg_in['data'] == 'C0FEBAB1':
            tcp_json_com.send({'data': 'DEADBEEF' })
            tcp_json_com.io.sock.close()
        else:
            tcp_json_com.send({'data': 'retry' })

json_coffee_communicator = PipeClient().register_custom_communicator(
  json_coffee_communicator, com_type='json')
print(json_coffee_communicator)
```
Output.
```text
<function PipeClient.communicator_proxy_factory.<locals>.communicator_proxy at 0x7f5308aa3ac0>
```

When the communicator proxy is invoked a communication channel is open with the pipe server and the remote communication routine on the server side is called with a `pipe_server.JavaTcpJsonCom` instance as argument and the function proxy return a `TcpJsonCom` instance. These two objects in each side wrap a client socket connected to each other and provide JSON communication helper methods (`send`, `recv`).

```python
tcp_json_com = json_coffee_communicator()
print(tcp_json_com)
print(tcp_json_com.io)
print(tcp_json_com.io.sock)
```
Output.
```text
<ghidra_pipe.pipe_client.TcpJsonCom object at 0x7f5308977fa0>
<ghidra_pipe.pipe_client.TcpNetIo object at 0x7f5308977c40>
<socket.socket fd=3, family=AddressFamily.AF_INET, type=SocketKind.SOCK_STREAM, proto=0, laddr=('127.0.0.1', 46422), raddr=('127.0.0.1', 5098)>

```

Next the communication with the remote routine is easy.

```python
print( tcp_json_com.recv() )
tcp_json_com.send({'data': 'C0FEBAB1'})
print(tcp_json_com.recv())
```
Output.
```text
{'data': 'C0DEC0FE'}
{'data': 'DEADBEEF'}
```

Use the underlying socket to close the communication.

```python
tcp_json_com.io.sock.close()
```


## Reach Existing Remote Object from Everywhere Through Proxy

Remote existing object declared in the global namespace of the pipe server as class, object and communicator can be reach from anywhere via the following pipe client proxy interface:
- `PipeClient.func_proxy_factory`
- `PipeClient.class_proxy_factory`
- `PipeClient.obj_proxy_factory`
- `PipeClient.communicator_proxy_factory`.

Example to reach a function previously declared.

```python
from ghidra_pipe import PipeClient


def foo():
  print(sys.version)


foo = PipeClient().register_func(foo)
foo()
```
Output.
```text
2.7.2 (v2.7.2:925a3cc3b49d, Mar 21 2020, 10:03:58)
[OpenJDK 64-Bit Server VM (Oracle Corporation)]
```

Reach this object from another place.

```text
>>> from ghidra_pipe import PipeClient
>>> foo = PipeClient().func_proxy_factory('foo')
>>> foo()
2.7.2 (v2.7.2:925a3cc3b49d, Mar 21 2020, 10:03:58)
[OpenJDK 64-Bit Server VM (Oracle Corporation)]
```


## Proxy Remote Object Tracking Information

For each remote function, class, object or custom communicator declared in the remote global namespace of the pipe server a proxy is returned by the pipe client interface. Each proxy keep track of basic information about the target pipe server and the remote object via the following attributes: `__PROXY_IP__`, `__PROXY_PORT__`, `__PROXY_OBJECT_NAME__`, `__PROXY_SRC__`. Example with a remote function.

```python
from ghidra_pipe import PipeClient

def foo():
    pass

foo = PipeClient().register_func(foo)

print(foo.__PROXY_IP__)
print(foo.__PROXY_PORT__)
print(foo.__PROXY_OBJECT_NAME__)
print("-"*80)
print(foo.__PROXY_SRC__)
```
Output.
```text
localhost
5098
foo
--------------------------------------------------------------------------------
def foo():
    pass
```

Keep in mind that if an object is redefined on a target remote pipe server, all object proxy which bind this object have the `__PROXY_SRC__` attribute de-synchronised with the remote object, because this information was not updated at runtime.


## File Copy Through Pipe

The pipe client interface provides a way to copy file from local to remote, from remote to local, from local bytes buffer to remote file and remote file to local bytes buffer. 

Copy a local file on the remote pipe server filesystem.

```text
>>> from ghidra_pipe import PipeClient
>>>
>>> with open('/tmp/local_file.bin', 'wb') as f:
...     f.write(b'\xDE\xAD\xC0\xDE')
... 
4
>>> PipeClient().file_transfer_to_server('/tmp/local_file.bin', '/tmp/remote_file.bin')
```

Copy a remote file from remote pipe server filesystem to local.

```text
>>> PipeClient().file_transfer_to_client('/tmp/remote_file.bin', '/tmp/local_file_comeback.bin')
4
>>> with open('/tmp/local_file_comeback.bin', 'rb') as f:
...      f.read()
... 
b'\xde\xad\xc0\xde'
```

Copy a local bytes buffer to a file on the remote pipe server filesystem.

```text
>>> PipeClient().file_bytes_transfer_to_server(b'\xC0\xFE\xBA\xB1', '/tmp/bytes_remote_file.bin')
```

Copy a file on the remote pipe server filesystem to local bytes buffer.

```text
>>> PipeClient().file_bytes_transfer_to_client('/tmp/bytes_remote_file.bin')
bytearray(b'\xc0\xfe\xba\xb1')
```

## Pipe Server JSON RPC Interface

The pipe server expose a [JSON RPC V2](https://www.jsonrpc.org/specification) Interface. The batch mode is not implemented. The pipe server is mono thread and process only one client at time. One RPC method is processed by connection.  The JSON frames exchanged by the client and the server are length prefixed as following. This frame encoding scheme is very simply and can be implemented in any language.

```text
    4 bytes
+----------------+-------------------- // --------------------+
|  JSON LENGTH   |                JSON MESSAGE                |
+----------------+-------------------- // --------------------+
```

As described in the JSON RPC V2 documentation the RPC requests take the following forms:
```text
{'jsonrpc': '2.0', 'id': <unique_request_identifier>, 'method': <method_name>, 'params': {}}
```

And the RPC notification take the following forms:
```text
{'jsonrpc': '2.0', 'method': <method_name>, 'params': {}}
```


The following RPC methods are available via RPC request:
- get_server_banner
- code_exec
- func_exec
- object_proxy_new
- object_proxy_getattr
- object_proxy_setattr
- remote_shutdown
- register_custom_communicator

The following RPC methods are available via RPC notification:
- execute_custom_communicator
- file_transfer_to_client
- file_transfer_to_server

All the pipe server RPC methods are described in the following document [json_rpc_api_pipe_server.md](./json_rpc_api_pipe_server.md)


## Development

Install the package in develop mode with the `DEV` identifier.

```text
$ git clone https://github.com/vincentdary/ghidra-pipe
$ cd ghidra_pipe
$ pip install -e .[DEV]
```

For coverage information for both pipe client and server side install coverage in Jython and in Python2 (Required because Jython coverage do not support report generation). 
```text
$ jython -m pip install coverage==5.6b1
$ python2 -m pip install coverage==4.3.4
```

Run the tests.

```text
$ cd ghidra_pipe/test/  && ./run_tests.sh
```

For coverage information run the test with the coverage flag.

```text
$ cd ghidra_pipe/test/ && ./run_tests.sh --coverage
```

See the coverage of the pipe client code.

```text
$ firefox  pipe_client_coverage/htmlcov/index.html &
```

See the coverage of the pipe server code. 

```text
$ cd pipe_server_coverage/ && coverage2 html
$ firefox pipe_server_coverage/htmlcov/index.html &
```

## FAQ

### Why an Another Tool

The author was charmed by [Ghidra Bridge](https://github.com/justfoxing/ghidra_bridge), but the tool was not working as expected (very slow) and was not expose the desired interface. That's why this new tool was created, with fewer functionalities but with different technical choices and much less code.

### Why the Pipe Server use Java Socket

The pipe server use Java socket based on `java.net` instead of the socket library of Jython. The reason of this choice is caused by the slowness of the Jython socket interface (based on `io.netty`) due to the conversion of Java bytes to Python bytes. In any case the conversion Java/Python bytes with tostring /fromstring must be avoided for large data length when it is possible to avoid bottlenecks. The pipe server gets around this problem for exceptional cases when it is necessary by dropping and loading the content of Java/Python byte array in temporary file. It is a bit dirty, but it allows avoiding bottlenecks.

### Why Ghidra-Pipe no Proxify Ghidra API in the Client Side Global Namespace

Bind the Ghidra API in the global namespace of the pipe client can be more convenient for REPL purpose and can allow less boilerplate code to access Ghidra Jython API. [Ghidra Bridge](https://github.com/justfoxing/ghidra_bridge) provides this features. However, this choice has disastrous performance because for each method call or attribute access on remote object an underlying request must be sent to the server proxy which includes at least request/response serialization/deserialization and request processing. For example, to perform comparison between two remote object of type GenericAdresse this will involve several network exchanges and server/client processing before to obtain the result. This proxy mechanism slow by design is not suitable or unusable for large Ghidra script. Moreover, provide this feature correctly requires implementing a lot of mechanics. This is why Ghidra-Pipe has chosen to not implement this feature.
