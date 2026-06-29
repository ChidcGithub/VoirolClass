import multiprocessing
import sys
from multiprocessing.connection import Client, Listener

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QSurfaceFormat
from PyQt6.QtWidgets import QApplication


class SplashProcess:
    def __init__(self):
        self._listener = Listener(("localhost", 0), authkey=b"voirol")
        port = self._listener.address[1]

        self._process = multiprocessing.Process(
            target=_run,
            args=(port,),
            daemon=True,
        )
        self._process.start()
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


def _run(port: int):
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)

    from voirol.gui.splash import StartupSplash

    splash = StartupSplash()
    splash.show()

    conn = Client(("localhost", port), authkey=b"voirol")
    close_pending = False

    def poll():
        nonlocal close_pending
        if conn.poll(0.01):
            try:
                msg = conn.recv()
                tp = msg.get("type")
                if tp == "status":
                    splash.set_status(msg.get("text", ""))
                elif tp == "error":
                    splash.set_error(msg.get("text", ""))
                elif tp == "close":
                    delay = msg.get("delay", 0)
                    if delay > 0 and not close_pending:
                        close_pending = True
                        QTimer.singleShot(delay, app.quit)
                    elif delay == 0:
                        app.quit()
            except (EOFError, ConnectionResetError):
                app.quit()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(50)

    sys.exit(app.exec())
