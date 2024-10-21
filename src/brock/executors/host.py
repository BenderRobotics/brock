import subprocess
import os
import sys
import platform

from typing import Optional, Union, Sequence
from brock.executors import Executor
from brock.config.config import Config
from brock.exception import ExecutorError


class HostExecutor(Executor):
    '''Executor for local host access'''

    def __init__(self, config: Config, name: str):
        '''Initializes Host executor

        :param config: A whole brock configuration
        :param name: Name of the executor
        '''
        super().__init__(config, name)

        self.help = 'Execute command on host computer'

        if self._default_shell is None:
            if platform.system() == 'Windows':
                self._default_shell = 'cmd'
            else:
                self._default_shell = 'sh'

    def exec(
        self,
        command: Union[str, Sequence[str]],
        chdir: Optional[str] = None,
        env_options: Optional[dict] = None
    ) -> int:
        if env_options is not None:
            os.environ.update(env_options)

        os.environ['PYTHONUNBUFFERED'] = '1'

        self._log.extra_info(f'Executing command on host: {command}')
        if not chdir:
            chdir = '.'

        try:
            proc = subprocess.Popen(
                command,
                cwd=os.path.join(self._base_dir, chdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            raise ExecutorError(f"Unable to run '{command}', binary not found")

        while proc.poll() is None:
            line = proc.stdout.readline()  # type:ignore
            if line:
                print(line.decode(), end='')

            line = proc.stderr.readline()  # type:ignore
            if line:
                print(line.decode(), end='', file=sys.stderr)

        return proc.returncode
