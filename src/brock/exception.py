class BaseBrockException(Exception):
    ERROR_CODE = -1

    def __init__(self, message: str = ''):
        self.message = message


class ConfigError(BaseBrockException):
    ERROR_CODE = 10


class UsageError(BaseBrockException):
    ERROR_CODE = 20


class ExecutorError(BaseBrockException):
    ERROR_CODE = 30
