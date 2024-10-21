import hashlib
from typing import Optional, Union, Sequence, Dict, Any
from brock.log import get_logger
from brock.config.config import Config
from brock.exception import ExecutorError


class Executor:
    '''Abstract class for all executors

    Provides the common functions all executors must implement or use default
    implementation defined here.
    '''

    def __init__(self, config: Config, name: str):
        self._log = get_logger()

        self._base_dir = config.base_dir
        self._hashed_base_dir = hashlib.md5(self._base_dir.encode('ascii')).hexdigest()

        self._conf = config.executors.get(name)
        self._default_shell = None

        self._env_vars = {
            'BROCK_HOST_PATH': config.work_dir,
            'BROCK_HOST_PROJECT_PATH': config.base_dir,
            'BROCK_RELATIVE_PATH': config.work_dir_rel,
        }

        self.help = ''

        if self._conf is not None:
            self._default_shell = self._conf.get('default_shell')
            self.help = self._conf.get('help', '')

    @property
    def default_shell(self) -> Optional[str]:
        return self._default_shell

    @property
    def env_vars(self) -> Dict:
        return self._env_vars

    def sync_in(self):
        '''Synchronizes local data to executor if needed'''
        pass

    def sync_out(self):
        '''Synchronizes local data out of executor if needed'''
        pass

    def status(self) -> str:
        return 'Idle'

    def stop(self):
        pass

    def restart(self):
        return 0

    def update(self):
        pass

    def exec(
        self,
        command: Union[str, Sequence[str]],
        chdir: Optional[str] = None,
        env_options: Optional[dict] = None
    ) -> int:
        raise NotImplementedError

    def shell(self) -> int:
        '''Opens a shell session, if available'''
        raise ExecutorError("This executor doesn't support direct shell access")
