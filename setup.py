import sys
from cx_Freeze import setup, Executable

base = None
if sys.platform == "win32":
    base = "Win32GUI"  # 或 "Win32GUI"

app_icon = "app_icon.ico"

setup(
    name="Gesture Password",
    version="0.1",
    description="Gesture Password",
    executables=[Executable(
        "code.py",  # 你的主脚本
        base=base,
        icon=app_icon  # 指定图标文件
    )],
)