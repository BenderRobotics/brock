import os
import hiyapyco
from schema import Schema, And, Use, Optional, SchemaError
from munch import Munch

from brock.exception import ConfigError
from brock.log import getLogger


class Config(Munch):
    SCHEMA = {
        'project': {
            'name': And(Use(str)),
            'base_path': And(Use(str))
        },
        'toolchain': {
            'image': And(Use(str)),
            Optional('default_cmd'): And(Use(str))
        }
    }

    def __init__(self, config_file_name=".brock.yml"):
        self._config_file_name = config_file_name
        self._log = getLogger()

        self.update(self.load())

    def load(self):
        # scan for config files
        config_files = self._scan_files()
        if not config_files:
            raise ConfigError("No config files found")

        # merge config files
        try:
            self._log.extra_info("Merging config files")
            conf = hiyapyco.load(config_files)
            self._log.debug(f"Merged config: {conf}")
        except hiyapyco.HiYaPyCoImplementationException as ex:
            raise ConfigError(f"Failed to process config files: {ex}")

        # validate config schema
        try:
            conf_schema = Schema(self.SCHEMA)
            conf_schema.validate(conf)
        except SchemaError as ex:
            raise ConfigError(f"Invalid config file: {ex}")

        return Munch.fromDict(conf)

    def _scan_files(self):
        cwd = os.getcwd()

        self._log.extra_info(f"Scanning config files, current dir: {cwd}")

        config_files = []
        path_parts = self._split_path(cwd)
        for i in range(1, len(path_parts) + 1):
            path = os.path.join(*path_parts[:i], self._config_file_name)
            if os.path.isfile(path):
                self._log.debug(f"Found config file: {path}")
                config_files.append(path)

        return config_files

    @classmethod
    def _split_path(cls, path):
        all_parts = []
        while True:
            parts = os.path.split(path)
            if parts[0] == path:    # sentinel for absolute paths
                all_parts.insert(0, parts[0])
                break
            elif parts[1] == path:  # sentinel for relative paths
                all_parts.insert(0, parts[1])
                break
            else:
                path = parts[0]
                all_parts.insert(0, parts[1])

        return all_parts
