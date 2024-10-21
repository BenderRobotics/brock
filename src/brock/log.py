import logging
import os
import sys
import platform

from colorama import Fore, Style
from colorama.initialise import wrap_stream
from logging import StreamHandler


class ColoredStreamHandler(StreamHandler):
    """
    Colored logger output.
    """

    def __init__(self, stream=None):
        StreamHandler.__init__(self, stream)

    COLORS = {
        'DEBUG': Fore.CYAN,
        'EXTRA_INFO': Fore.GREEN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW + Style.BRIGHT,
        'ERROR': Fore.RED + Style.BRIGHT,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }

    def emit(self, record):
        message = self.format(record)
        try:
            self.stream.write(self.COLORS[record.levelname] + message + Style.RESET_ALL + '\n')
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)


class DefaultFormatter(logging.Formatter):
    def __init__(self, fmt=">> %(message)s"):
        logging.Formatter.__init__(self, fmt)

    def format(self, record):
        orig_format = self._fmt

        ret = logging.Formatter.format(self, record)

        self._fmt = orig_format

        return ret


def colored_handler_factory():
    """
    Factory method for custom stream handler that supports
    colored output on GitlabRunner and correct platform recognition.
    """

    on_windows = platform.system() == 'Windows'
    on_gitlab_ci = os.environ.get('GITLAB_CI', False)

    if on_windows and not on_gitlab_ci:
        log_stream = wrap_stream(sys.stdout, None, None, None, True)
    else:
        log_stream = sys.stdout

    return ColoredStreamHandler(log_stream)


DEFAULT_LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'base_formatter': {
            '()': 'brock.log.DefaultFormatter',
        },
    },
    'handlers': {
        'color_handler': {
            '()': 'brock.log.colored_handler_factory',
            'level': 'DEBUG',
            'formatter': 'base_formatter',
        },
        'normal_handler': {
            'formatter': 'base_formatter',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        'color': {
            'level': 'DEBUG',
            'handlers': ['color_handler'],
            'propagate': False,
        },
        'normal': {
            'level': 'INFO',
            'handlers': ['normal_handler'],
            'propagate': False,
        },
    },
}

INFO = logging.INFO
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
ERROR = logging.ERROR
WARNING = logging.WARNING
WARN = logging.WARN
INFO = logging.INFO
EXTRA_INFO = logging.INFO - 5
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

LOGGER = 'color'
VERBOSITY = INFO

logging._levelToName[EXTRA_INFO] = 'EXTRA_INFO'
logging._nameToLevel['EXTRA_INFO'] = EXTRA_INFO


class Logger(logging.getLoggerClass()):
    def extra_info(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'INFO'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.info("Houston, we have a %s", "interesting problem", exc_info=1)
        """
        if self.isEnabledFor(EXTRA_INFO):
            self._log(EXTRA_INFO, msg, args, **kwargs)


logging.Logger
logging.setLoggerClass(Logger)


def getLogger():
    logger = Logger.manager.getLogger(LOGGER)
    logger.setLevel(VERBOSITY)

    return logger
