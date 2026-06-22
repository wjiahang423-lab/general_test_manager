@echo off
set PYTHONHOME=
set PYTHONPATH=
C:\Users\wy_wangbo\AppData\Local\Programs\Python\Python310\python.exe D:\Siada\general_test_manager\_gen_rzcu_yaml.py > D:\Siada\general_test_manager\_gen_stdout.txt 2> D:\Siada\general_test_manager\_gen_stderr.txt
echo exit_code=%errorlevel% >> D:\Siada\general_test_manager\_gen_stderr.txt
