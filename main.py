"""
通用测试管理工具 — 入口点
"""

import sys
import os

# Ensure the project root is on sys.path regardless of how main.py is launched
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# When running from a PyInstaller onedir bundle, data files are in sys._MEIPASS
_DATA_ROOT = getattr(sys, "_MEIPASS", _HERE)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from app.ui.main_window import MainWindow


def _app_icon() -> QIcon:
    ico = os.path.join(_DATA_ROOT, "resources", "app.ico")
    if os.path.isfile(ico):
        return QIcon(ico)
    return QIcon()


def main() -> None:
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setApplicationName("通用测试管理工具")
    app.setWindowIcon(_app_icon())

    win = MainWindow()
    win.setWindowIcon(_app_icon())
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
