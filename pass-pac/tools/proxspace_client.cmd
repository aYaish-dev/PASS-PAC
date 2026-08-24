@echo off
setlocal

if /I not "%~2"=="-c" exit /b 2
if /I "%~3"=="hw version" goto run_command
if /I "%~3"=="hw status" goto run_command
if /I "%~3"=="hw tune" goto run_command
if /I "%~3"=="hf search" goto run_command
if /I "%~3"=="lf search" goto run_command
if /I "%~3"=="hf 14a info" goto run_command
if /I "%~3"=="emv pse -s2" goto run_command
if /I "%~3"=="emv search -s" goto run_command
if /I "%~3"=="emv reader" goto run_command
if /I "%~3"=="emv list" goto run_command
if /I "%~3"=="hf mf info" goto run_command
if /I "%~3"=="hf mfu info" goto run_command
if /I "%~3"=="hf 15 info" goto run_command
if /I "%~3"=="hf mfdes info" goto run_command
if /I "%~3"=="hf iclass info" goto run_command
if /I "%~3"=="lf em 410x reader" goto run_command
if /I "%~3"=="lf hid reader" goto run_command
if /I "%~3"=="lf t55xx info" goto run_command
if /I "%~3"=="trace list -t 14a" goto run_command
if /I "%~3"=="trace list -t mf" goto run_command
if /I "%~3"=="trace list -t des" goto run_command
if /I "%~3"=="trace list -t 7816" goto run_command
if /I "%~3"=="trace list -t 15" goto run_command
if /I "%~3"=="trace list -t iclass" goto run_command
exit /b 2

:run_command
cd /d C:\ProxSpace
call setup\setup.cmd
call msys2\msys2_shell.cmd -mingw64 -defterm -no-start -c "cd /pm3/proxmark3 && ./client/proxmark3.exe --incognito %~1 -c '%~3'"
exit /b %ERRORLEVEL%
