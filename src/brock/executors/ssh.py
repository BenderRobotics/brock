import os
from typing import Optional, Union, Sequence
from fabric import Connection
from brock.executors import Executor
from brock.config.config import Config
from brock.exception import ExecutorError


class SshExecutor(Executor):
    '''Executor for launching commands on the remote system over ssh'''

    def __init__(self, config: Config, name: str):
        '''Initializes SSH executor

        :param config: A whole brock configuration
        :param name: Name of the executor
        '''
        super().__init__(config, name)

        self._host = self._conf.host
        self._username = self._conf.get('username')
        self._password = self._conf.get('password')

        if self._default_shell is None:
            self._default_shell = 'sh'

    def exec(
        self,
        command: Union[str, Sequence[str]],
        chdir: Optional[str] = None,
        env_options: Optional[dict] = None
    ) -> int:

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
                host=self._host, user=username, connect_kwargs={
                    'password': password,
                }, inline_ssh_env=True
            )

            if env_options is not None:
                result = conn.run(cmd, hide=True, env=env_options)
            else:
                result = conn.run(cmd, hide=True)
            print(result.stdout, end='')

            return result.exited
        except Exception as ex:
            raise ExecutorError(f'Failed to run command: {ex}')
