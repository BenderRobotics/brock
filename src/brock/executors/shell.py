from typing import Optional

import subprocess
import os
from brock.exception import ExecutorError
from brock.executors import Executor


class ShellExecutor(Executor):
    '''Executor for local console access'''

    def exec(self, command: str, chdir: Optional[str] = None) -> int:
        os.environ['PYTHONUNBUFFERED'] = '1'

        self._log.extra_info(f'Executing command in host shell: {command}')
        if not chdir:
            chdir = '.'

        proc = subprocess.Popen(
            command,
            cwd=chdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        while proc.poll() is None:
            line = proc.stdout.readline()  # type:ignore
            if line:
                self._log.stdout(line.decode().replace('\n', ''))

            line = proc.stderr.readline()  # type:ignore
            if line:
                self._log.stderr(line.decode().replace('\n', ''))
        return proc.returncode
