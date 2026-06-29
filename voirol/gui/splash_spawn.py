import subprocess
import sys
from multiprocessing.connection import Listener


class SplashProcess:
    def __init__(self):
        self._listener = Listener(("localhost", 0), authkey=b"voirol")
        port = self._listener.address[1]

        flags = 0
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS
        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--splash", str(port)]
        else:
            args = [sys.executable, sys.argv[0], "--splash", str(port)]
        self._process = subprocess.Popen(
            args,
            creationflags=flags,
        )
        self._conn = self._listener.accept()

    def set_status(self, text: str):
        try:
            self._conn.send({"type": "status", "text": text})
        except Exception:
            pass

    def set_error(self, text: str):
        try:
            self._conn.send({"type": "error", "text": text})
        except Exception:
            pass

    def close(self):
        try:
            self._conn.send({"type": "close", "delay": 0})
        except Exception:
            pass

    def close_with_delay(self, ms: int = 500):
        try:
            self._conn.send({"type": "close", "delay": ms})
        except Exception:
            pass
