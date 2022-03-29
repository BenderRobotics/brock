from typing import Optional, Union, Sequence
from brock.log import getLogger
from brock.config.config import Config
from brock.exception import ExecutorError


class Executor:
    '''Abstract class for all executors

    Provides the common functions all executors must implement or use default
    implementation defined here.
    '''

    def __init__(self, config: Config, name: str, help: Optional[str] = None):
        self._log = getLogger()
        self.help = help

        our_conf = config.executors.get(name, None)
        if our_conf is not None:
            self._default_shell = our_conf.get('default_shell', None)
        else:
            self._default_shell = None

    def get_default_shell(self) -> Optional[str]:
        return self._default_shell

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

    def update(self):
        pass

    def exec(self, command: Union[str, Sequence[str]], chdir: Optional[str] = None) -> int:
        raise NotImplementedError

    def shell(self) -> int:
        '''Opens a shell session, if available'''
        raise ExecutorError("This executor doesn't support direct shell access")
