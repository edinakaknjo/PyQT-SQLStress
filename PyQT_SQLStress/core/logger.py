import time, threading
from typing import List
from PyQt5 import QtCore

class LogBuffer(QtCore.QObject):
    updated = QtCore.pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._lines: List[str] = []
        self._lock = threading.Lock()
    def log(self, msg: str):
        with self._lock:
            ts = time.strftime("%H:%M:%S")
            line = f"[{ts}] {msg}"
            self._lines.append(line)
        self.updated.emit(line)
    def get_all(self):
        with self._lock:
            return "\n".join(self._lines[-1000:])
