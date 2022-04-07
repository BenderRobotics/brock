import subprocess
import os
import sys
import platform

from typing import Optional, Union, Sequence
from brock.executors import Executor
from brock.config.config import Config


class HostExecutor(Executor):
    '''Executor for local host access'''

    def __init__(self, config: Config, name: str, help: Optional[str] = None):
        '''Initializes Host executor

        :param config: A whole brock configuration
        :param name: Name of the executor
        :param help: Optional help message
        '''
        super().__init__(config, name, help)

        self._base_dir = config.base_dir

        if self._default_shell is None:
            if platform.system() == 'Windows':
                self._default_shell = 'cmd'
            else:
                self._default_shell = 'sh'

    def exec(self, command: Union[str, Sequence[str]], chdir: Optional[str] = None) -> int:
        os.environ['PYTHONUNBUFFERED'] = '1'

        self._log.extra_info(f'Executing command on host: {command}')
        if not chdir:
            chdir = '.'

        proc = subprocess.Popen(
            command,
            cwd=os.path.join(self._base_dir, chdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        while proc.poll() is None:
            line = proc.stdout.readline()  # type:ignore
            if line:
                print(line.decode(), end='')

            line = proc.stderr.readline()  # type:ignore
            if line:
                print(line.decode(), end='', file=sys.stderr)

        return proc.returncode
