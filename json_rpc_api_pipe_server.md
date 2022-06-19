
# Pipe Server RPC Methods

* [get_server_banner](#get_server_banner)
* [code_exec](#code_exec)
* [func_exec](#func_exec)
* [object_proxy_new](#object_proxy_new)
* [object_proxy_getattr](#object_proxy_getattr)
* [object_proxy_setattr](#object_proxy_setattr)
* [remote_shutdown](#remote_shutdown)
* [register_custom_communicator](#register_custom_communicator)
* [execute_custom_communicator](#execute_custom_communicator)
* [file_transfer_to_client](#file_transfer_to_client)
* [file_transfer_to_server](#file_transfer_to_server)

## get_server_banner

Get the JSON RPC server banner.

RPC request:
- method: `get_server_banner`

RPC response:
- result:
  - `banner` (string): The banner of the RPC server.

## code_exec

Execute Python code in the remote global namespace of the pipe server.

RPC request:
- method: `code_exec`
- params: 
  - `code` (string): Python source code to execute.
  - `std_cap` (boolean): Capture flag for the standard output/error.
  - `std_forward` (boolean): Forward flag to redirect stdout/err. If this flag is activated stdout and std error of the code executed if forward to the client in live via JSON messages with the following form `{"live_stdout": "stdout content"}`/`{"live_stderr": "stderr content"}`.

RPC response:
- result:
  - `output` (string): The captured standard output/error as string.

RPC error response:
- code: `-3200`
- data: 
  - `ip` (string): IP of the pipe server.
  - `port` (integer): Port of the pipe server.
  - `stacktrace` (string): Python stack trace of the executed code.
  - `code` (string): Executed code as string.

## func_exec

Invoke a Python function existing in the remote global namespace of the pipe server.

RPC request:
- method: `func_exec`
- params: 
  - `name` (string): Name of an existing Python function to invoke.
  - `args` (list): List of arguments pass to the invoked function.
  - `kwargs` (dict): List of keyword arguments pass to the invoked function.
  - `std_forward` (boolean): Forward flag to redirect stdout/err. If this flag is activated stdout and std error of the code executed if forward to the client in live via JSON messages with the following form `{"live_stdout": "stdout content"}`/`{"live_stderr": "stderr content"}`.

RPC response:
- result:
  - `return` (any type): Return value of the invoked function.

RPC error response:
- code: `-3200`
- data: 
  - `ip` (string): IP of the pipe server.
  - `port` (integer): Port of the pipe server.
  - `stacktrace` (string): Python stack trace of the executed code.
  - `code` (string): Executed code as string.

## object_proxy_new

Create a new Python object in the remote global namespace of the pipe server.

RPC request:
- method: `object_proxy_new`
- params: 
  - `class_name` (string): class invoked to create the new object. 
  - `args` (list): List of arguments pass to the invoked class.
  - `kwargs` (dict): List of keyword arguments pass to the invoked class.
  - `std_forward` (boolean): Forward flag to redirect stdout/err. If this flag is activated stdout and std error of the code executed if forward to the client in live via JSON messages with the following form `{"live_stdout": "stdout content"}`/`{"live_stderr": "stderr content"}`.

RPC response:
- result:
  - `object_name` (string): Name of the new created object chosen by the pipe server.

RPC error response:
- code: `-32000`
- data: 
  - `ip` (string): IP of the pipe server.
  - `port` (integer): Port of the pipe server.
  - `stacktrace` (string): Python stack trace of the executed code.
  - `code` (string): Executed code as string.

## object_proxy_getattr

Get an object attribute of a Python object existing in the remote global namespace of the pipe server.

RPC request:
- method: `object_proxy_getattr`
- params: 
  - `object_name` (string): Object name.
  - `name` (string): Attribute name.

RPC response:
- result:
  - `type` (string): Python type of the attribute as string.
  - `value` (any type): The value of the attribute.


## object_proxy_setattr

Set an object attribute value of a Python object existing in the remote global namespace of the pipe server.


RPC request:
- method: `object_proxy_setattr`
- params: 
  - `object_name` (string): Object name.
  - `name` (string): Attribute name.
  - `value` (any type): The value set to the attribute.

## remote_shutdown

Shutdown the RPC server.

RPC request:
- method: `remote_shutdown`


## register_custom_communicator

Register a custom Python communication routine.

RPC request:
- method: `register_custom_communicator`
- params: 
  - `code` (string): Source code of the communication routine.
  - `communicator_name` (string): Name bind to the communication routine.

RPC error response:
- code: `-32000`
- data: 
  - `ip` (string): IP of the pipe server.
  - `port` (integer): Port of the pipe server.
  - `stacktrace` (string): Python stack trace of the executed code.
  - `code` (string): Executed code as string.

## execute_custom_communicator

Invoke a registered custom communicator via an RPC notification. Since this is a notification no JSON response is returned. After the notification is received by the RPC server the connection is keep up. The  `execute_custom_communicator` method search for the requested custom communicator, if it is found, one byte with the value `0x00` is sent to the client. Else the value `0xff` is sent and the communication is closed. If the routine is found, it is invoked and the current socket used by the client for the RPC notification is pass to the communication routine wrapped in an `JavaTcpNetIo` or `JavaTcpJsonCom` Python object.

RPC notification:
- method: `execute_custom_communicator`
- params:
  - `communicator_name` (string): Name bind to the communication routine.
  - `com_type` (string): Communication type (`binary`, `json`) used by the custom communicator. According to this value the communication routine is invoked with an `JavaTcpNetIo` or `JavaTcpJsonCom` Python object wrapping the underlying socket used for the connection.


## file_transfer_to_client

Transfer a file to a client. Since this is a notification no JSON response is returned. After the notification is received by the RPC server, the `file_transfer_to_client` method search for he requested file, if it is found, one byte with the value `0x00` is sent to the client. Else the value `0xff` is sent and the communication is closed.  After this byte is sent by the server the size in byte of the file is sent as 8 bytes in big endian followed by the file bytes.

RPC notification:
- method: `file_transfer_to_client`
- params:
  - `src_file` (string): File name on the pipe server filesystem to transfer to the client. 


## file_transfer_to_server

Transfer a file to the pipe server file system. After the notification is received by the RPC server, the `file_transfer_to_server` method wait for the file bytes. When all the bytes of the file are received the server send one byte to the client with the value `0xff`.

RPC notification:
- method: `file_transfer_to_server`
- params:
  - `dst_file` (string): File name which will be written on the pipe server filesystem. 
  - `data_length` (integer): Size in byte of the file.