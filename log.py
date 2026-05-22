import logging
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

RESET = "\033[0m"
LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARN": "\033[33m",
    "ERROR": "\033[31m",
    "HTTP": "\033[34m",
}
MODULE_COLORS = {
    "LLM": "\033[35m",
    "TELEGRAM": "\033[36m",
    "DATA": "\033[34m",
    "ANALYSIS": "\033[33m",
    "CACHE": "\033[32m",
    "SCHEDULER": "\033[37m",
}

HTTP_LEVEL = 15
logging.addLevelName(HTTP_LEVEL, "HTTP")


def _http(self, message, *args, **kwargs):
    if self.isEnabledFor(HTTP_LEVEL):
        self._log(HTTP_LEVEL, message, args, **kwargs)


logging.Logger.http = _http


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        ts = datetime.fromtimestamp(record.created, tz=_ET).strftime("%H:%M:%S ET")
        level_name = record.levelname
        lc = LEVEL_COLORS.get(level_name, RESET)
        module = record.__dict__.get("module_tag", record.name.split(".")[-1].upper())
        mc = MODULE_COLORS.get(module, RESET)
        msg = super().format(record)
        return f"{ts} {lc}{level_name:<6}{RESET} {mc}{module:<10}{RESET} {msg}"


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(ColoredFormatter("%(message)s"))

_logger = logging.getLogger("sora")
_logger.setLevel(logging.DEBUG)
_logger.handlers.clear()
_logger.addHandler(_handler)


def get_logger(name: str, module_tag: str = "") -> logging.Logger:
    logger = _logger.getChild(name)
    logger.module_tag = module_tag or name.split(".")[-1].upper()
    return logger
