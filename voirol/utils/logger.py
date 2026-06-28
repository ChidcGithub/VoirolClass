import gzip
import logging
import os
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal


class LogSignal(QObject):
    emitted = pyqtSignal(str)


_log_signal = LogSignal()


class QtLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            _log_signal.emitted.emit(msg)
        except RuntimeError:
            pass


_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str = "voirol") -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    logger = logging.getLogger(name)
    _loggers[name] = logger
    return logger


def _rotator(source: str, dest: str):
    with open(source, "rb") as f_in:
        with gzip.open(dest + ".gz", "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


def _namer(name: str) -> str:
    return name + ".gz"


def _compress_orphaned_logs(log_dir: str):
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return
    for f in sorted(log_dir.iterdir()):
        name = f.name
        if not name.startswith("voirol.log.") or name.endswith(".gz"):
            continue
        try:
            with open(f, "rb") as f_in:
                with gzip.open(str(f) + ".gz", "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            f.unlink()
        except Exception:
            pass


def setup_logger(log_dir: str = "logs", level: str = "INFO", max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5):
    log_path = Path(log_dir) / "voirol.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _compress_orphaned_logs(log_dir)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    existing = {type(h).__name__ for h in root.handlers}
    log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if "StreamHandler" not in existing:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(log_level)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    if "RotatingFileHandler" not in existing:
        fh = RotatingFileHandler(
            str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        fh.namer = _namer
        fh.rotator = _rotator
        root.addHandler(fh)

    if "QtLogHandler" not in existing:
        qh = QtLogHandler()
        qh.setLevel(logging.DEBUG)
        qh.setFormatter(fmt)
        root.addHandler(qh)
