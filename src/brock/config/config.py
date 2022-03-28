import os
import hiyapyco
from schema import Schema, And, Or, Use, Optional, SchemaError
from munch import Munch

from brock import __version__
from brock.exception import ConfigError
from brock.log import getLogger


class Config(Munch):
    SCHEMA = {
        'version': Use(str),
        'project': str,
        Optional('help'): str,
        Optional('default_cmd'): str,
        Optional('commands'): {
            Optional('default'): str,
            str: {
                Optional('default_executor'): str,
                Optional('chdir'): str,
                Optional('help'): str,
                Optional('depends_on'): [str],
                Optional('steps'): [Or(str, {
                    Optional('executor'): str,
                    Optional('shell'): str,
                    'script': str
                })],
            }
        },
        'executors': {
            Optional('default'):
                str,
            str:
                Or({
                    'type': 'docker',
                    Optional('help'): str,
                    Or('image', 'dockerfile', only_one=True): str,
                    Optional('platform'): str,
                    Optional('env'): {
                        str: Or(str, int, float)
                    },
                    Optional('devices'): [str],
                    Optional('sync'): {
                        'type': 'rsync',
                        Optional('exclude'): [str],
                    },
                    Optional('prepare'): [str],
                    Optional('default_shell'): str,
                }, {
                    'type': 'ssh',
                    Optional('help'): str,
                    'host': str,
                    Optional('username'): str,
                    Optional('password'): Use(str)
                })
        }
    }

    def __init__(self, config_file_name='.brock.yml'):
        self._config_file_name = config_file_name
        self._log = getLogger()

        self.update(self.load())
        current = __version__.split('.')
        config = str(self.version).split('.')
        for pos, val in enumerate(current):
            if config[pos] < val:
                break
            if config[pos] > val:
                raise ConfigError(
                    f'Current config requires Brock of version at least {self.version}, you are using {__version__}'
                )

    def load(self):
        # scan for config files
        config_files = self._scan_files()

        # merge config files
        try:
            self._log.extra_info('Merging config files')
            conf = hiyapyco.load(config_files, method=hiyapyco.METHOD_MERGE)
            self._log.debug(f'Merged config: {conf}')
        except hiyapyco.HiYaPyCoImplementationException as ex:
            raise ConfigError(f'Failed to process config files: {ex}')

        # validate config schema
        try:
            conf_schema = Schema(self.SCHEMA)
            conf_schema.validate(conf)
        except SchemaError as ex:
            raise ConfigError(f'Invalid config file: {ex}')

        return Munch.fromDict(conf)

    def _scan_files(self):
        self.work_dir = os.getcwd().replace('\\', '/')

        self._log.extra_info(f'Scanning config files, work dir: {self.work_dir}')

        config_files = []
        path_parts = self._split_path(self.work_dir)
        for i in range(1, len(path_parts) + 1):
            path = os.path.join(*path_parts[:i], self._config_file_name).replace('\\', '/')
            if os.path.isfile(path):
                self._log.debug(f'Found config file: {path}')
                config_files.append(path)

        if not config_files:
            raise ConfigError('No config files found')

        self.base_dir = os.path.dirname(config_files[0])
        self._log.debug(f'Base dir: {self.base_dir}')

        common_prefix = os.path.commonprefix([self.work_dir, self.base_dir])
        self.work_dir_rel = os.path.relpath(self.work_dir, common_prefix).replace('\\', '/')
        self._log.debug(f'Relative work dir: {self.work_dir_rel}')

        return config_files

    @classmethod
    def _split_path(cls, path):
        all_parts = []
        while True:
            parts = os.path.split(path)
            if parts[0] == path:  # sentinel for absolute paths
                all_parts.insert(0, parts[0])
                break
            elif parts[1] == path:  # sentinel for relative paths
                all_parts.insert(0, parts[1])
                break
            else:
                path = parts[0]
                all_parts.insert(0, parts[1])

        return all_parts
