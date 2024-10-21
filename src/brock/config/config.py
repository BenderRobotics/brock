import os
import hiyapyco
from schema import Schema, And, Or, Use, Optional, Regex, SchemaError
import typing as t
from munch import Munch
from pathlib import Path

from brock import __version__
from brock.exception import ConfigError
from brock.log import get_logger


class Config(Munch):
    SCHEMA = {
        'version': And(str, Regex(r'^[0-9]+.[0-9]+.[0-9]+$')),
        'project': str,
        Optional('help'): str,
        Optional('default_cmd'): str,
        Optional('commands', default={}): {
            Optional('default'): str,
            str: {
                Optional('default_executor'): str,
                Optional('chdir'): str,
                Optional('help'): str,
                Optional('depends_on'): [str],
                Optional('options'): {
                    Optional(str):
                        Or({
                            'flag': Use(str),
                            Optional('default'): any,
                            Optional('short_name'): any,
                            Optional('variable'): str,
                            Optional('help'): str
                        }, {
                            'argument': Use(str),
                            Optional('default'): any,
                            Optional('required'): bool,
                            Optional('choices'): [any],
                            Optional('variable'): str,
                            Optional('help'): str
                        }, {
                            Optional('option', default=True): Use(str),
                            Optional('default'): any,
                            Optional('short_name'): any,
                            Optional('choices'): [any],
                            Optional('variable'): str,
                            Optional('required'): bool,
                            Optional('help'): str
                        })
                },
                Optional('steps'): [Or(str, {
                    Optional('executor'): str,
                    Optional('shell'): str,
                    'script': str
                })],
            }
        },
        Optional('executors', default={}): {
            Optional('default'):
                str,
            Optional(str):
                Or({
                    'type':
                        'docker',
                    Optional('help'):
                        str,
                    Or('image', 'dockerfile', only_one=True):
                        str,
                    Optional('platform'):
                        str,
                    Optional('env'): {
                        str: Or(str, int, float)
                    },
                    Optional('mac_address'):
                        And(str, Regex(r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$')),
                    Optional('ports', default={}): {
                        Or(int, And(str, Regex(r'^\d+/(tcp|udp|sctp)'))): int
                    },
                    Optional('devices'): [str],
                    Optional('sync'):
                        Or(
                            {
                                'type': 'rsync',
                                Optional('options'): [str],
                                Optional('filter'): [str],
                                Optional('include'): [str],
                                Optional('exclude'): [str],
                            },
                            {'type': 'mutagen'},
                        ),
                    Optional('prepare'): [str],
                    Optional('default_shell'):
                        str,
                }, {
                    'type': 'ssh',
                    Optional('help'): str,
                    'host': str,
                    Optional('username'): str,
                    Optional('password'): Use(str)
                })
        }
    }

    def __init__(self, configs: t.Optional[t.List[str]] = None, config_file_names: t.Optional[t.List[str]] = None):
        self._log = get_logger()

        if configs is None:
            configs = self._scan_files(config_file_names)

        merged_config = self._load(configs)
        validated_config = self._validate(merged_config)

        self.update(Munch.fromDict(validated_config))

    def _load(self, configs: t.List[str]) -> Munch:
        try:
            self._log.extra_info('Merging config files')
            config = hiyapyco.load(configs, method=hiyapyco.METHOD_MERGE)
            self._log.debug(f'Merged config: {config}')
        except Exception as ex:
            raise ConfigError(f'Failed to process config files: {ex}')

        if config is None:
            raise ConfigError('Invalid config file: Config file is empty')

        return config

    def _validate(self, config: t.Dict) -> t.Dict:
        try:
            config_schema = Schema(self.SCHEMA)
            config = config_schema.validate(config)
        except SchemaError as ex:
            raise ConfigError(f'Invalid config file: {ex}')

        current_ver = __version__.split('.')
        config_ver = str(config['version']).split('.')
        for pos, val in enumerate(current_ver[0:3]):
            if int(config_ver[pos]) < int(val):
                break
            if int(config_ver[pos]) > int(val):
                raise ConfigError(
                    f'Current config requires Brock of version at least {config["version"]}, you are using {__version__}'
                )

        return config

    def _scan_files(self, file_names: t.Optional[t.List[str]] = None) -> t.List[str]:
        if file_names is None:
            file_names = ['.brock.yml', 'brock.yml', '.brock.yaml', 'brock.yaml']

        self.work_dir = os.getcwd().replace('\\', '/')

        self._log.extra_info(f'Scanning config files, work dir: {self.work_dir}')

        config_files = []
        path_parts = self._split_path(self.work_dir)

        for i in range(1, len(path_parts) + 1):
            found = 0
            for config_file_name in file_names:
                path = Path('').joinpath(*path_parts[:i], config_file_name)

                if path.is_file():
                    self._log.debug(f'Found config file: {path.as_posix()}')
                    config_files.append(path.as_posix())
                    found += 1

            if found > 1:
                raise ConfigError(
                    f"Multiple brock config files found in '{Path('').joinpath(*path_parts[:i]).as_posix()}'"
                )

        if not config_files:
            raise ConfigError(
                f"No config file ({', '.join(file_names)}) found in '{self.work_dir}' or parent directories"
            )

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
