class PackageException(Exception):
    ERROR_CODE = -1

    def __init__(self, message: str = ""):
        self.message = message
