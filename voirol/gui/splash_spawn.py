import os
import subprocess
import sys
from multiprocessing.connection import Listener


class SplashProcess:
    def __init__(self, authkey: bytes | None = None):
        if authkey is None:
            authkey = os.urandom(32)
        self._authkey = authkey
        self._listener = Listener(("localhost", 0), authkey=authkey)
        port = self._listener.address[1]

        flags = 0
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--splash", str(port), authkey.hex()]
        else:
            args = [sys.executable, sys.argv[0], "--splash", str(port), authkey.hex()]
        self._process = subprocess.Popen(
            args,
            creationflags=flags,
        )
        try:
            self._conn = self._listener.accept()
        except Exception:
            self._process.terminate()
            self._process.wait()
            self._listener.close()
            raise RuntimeError("Splash subprocess failed to connect")

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

    def terminate(self):
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except Exception:
            try:
                self._process.kill()
            except Exception:
                pass
        try:
            self._conn.close()
        except Exception:
            pass
        try:
            self._listener.close()
        except Exception:
            pass

    def __del__(self):
        self.terminate()
