import logging
import sys

_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str = "voirol") -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    _loggers[name] = logger
    return logger


def setup_file_logger(file_path: str, level: str = "INFO") -> None:
    logger = logging.getLogger("voirol")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.FileHandler(file_path, encoding="utf-8")
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
