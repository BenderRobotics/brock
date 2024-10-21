from typing import Optional
from brock.log import getLogger
from brock.exception import ExecutorError


class Executor:
    '''Abstract class for all executors

    Provides the common functions all executors must implement or use default
    implementation defined here.
    '''

    def __init__(self, config, name: str, help: Optional[str] = None):
        self._log = getLogger()
        self.help = help

    def on_exit(self):
        '''Called upon exiting the brock'''
        pass

    def update_logger(self):
        self._log = getLogger()

    def status(self) -> str:
        return 'Idle'

    def stop(self):
        pass

    def restart(self):
        return 0

    def exec(self, command: str, chdir: Optional[str] = None) -> int:
        raise NotImplementedError

    def shell(self) -> int:
        '''Opens a shell session, if available'''
        raise ExecutorError("This executor doesn't support direct shell access")
