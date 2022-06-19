@echo off

REM ############################################################################
REM
REM Copyright 2022 Vincent Dary
REM
REM This file is part of ghidra-pipe.
REM
REM ghidra-pipe is free software: you can redistribute it and/or modify it under
REM the terms of the GNU General Public License as published by the Free
REM Software Foundation, either version 3 of the License, or (at your option)
REM any later version.
REM
REM ghidra-pipe is distributed in the hope that it will be useful, but WITHOUT
REM ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
REM FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
REM more details.
REM
REM You should have received a copy of the GNU General Public License along with
REM ghidra-pipe. If not, see <https://www.gnu.org/licenses/>.
REM
REM #############################################################################

SET SCRIPT_DIR=%~dp0
SET PIPE_CLIENT_TESTS=%SCRIPT_DIR%\test_ghidra_pipe_client.py
SET JYTHON_BIN=C:\jython2.7.2\bin\jython.exe
SET PYTEST_BIN=C:\python_env_310\Scripts\pytest.exe

%PYTEST_BIN% --capture=no -v %PIPE_CLIENT_TESTS% %*
