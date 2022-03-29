from typing import Optional, Union, Sequence
from fabric import Connection
from brock.executors import Executor
from brock.config.config import Config
from brock.exception import ExecutorError


class SshExecutor(Executor):
    '''Executor for launching commands on the remote system over ssh'''

    def __init__(self, config: Config, name: str, help: Optional[str] = None):
        '''Initializes SSH executor

        :param config: A whole brock configuration
        :param name: Name of the executor
        :param help: Optional help message
        '''
        super().__init__(config, name, help)

        our_conf = config.executors[name]

        self._host = our_conf.host
        self._username = our_conf.get('username', None)
        self._password = our_conf.get('password', None)

        if self._default_shell is None:
            self._default_shell = 'sh'

    def exec(self, command: Union[str, Sequence[str]], chdir: Optional[str] = None) -> int:
        self._log.extra_info(f'Executing command on SSH host {self._host}: {command}')

        if type(command) is not str:
            command = ' '.join([f'"{c}"' if ' ' in c else c for c in command])

        if self._username is None:
            username = input('Enter username: ')
        else:
            username = self._username

        if self._password is None:
            password = input('Enter password: ')
        else:
            password = self._password

        if chdir is not None:
            self._log.debug(f'Work dir: {chdir}')
            cmd = f'cd {chdir}; {command}'
        else:
            cmd = command

        try:
            conn = Connection(
                host=self._host,
                user=username,
                connect_kwargs={
                    'password': password,
                },
            )

            result = conn.run(cmd, hide=True)

            self._log.stdout(result.stdout)

            return result.exited
        except Exception as ex:
            raise ExecutorError(f'Failed to run command: {ex}')
