import os
import hiyapyco
from schema import Schema, And, Use, Optional, SchemaError
from munch import Munch

from brock.exception import ConfigError
from brock.log import getLogger


class Config(Munch):
    SCHEMA = {
        'project': {
            'name': And(Use(str))
        },
        'toolchain': {
            'image': And(Use(str)),
            Optional('platform'): And(
                str, Use(str.lower),
                lambda s: s in ('linux', 'windows')),
            Optional('isolation'): And(
                str, Use(str.lower),
                lambda s: s in ('process', 'hyperv', 'default')),
            Optional('volume_sync'): And(
                str, Use(str.lower),
                lambda s: s in ('rsync', 'no')),
            Optional('sync_exclude'): [str],
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

        # merge config files
        try:
            self._log.extra_info("Merging config files")
            conf = hiyapyco.load(config_files, method=hiyapyco.METHOD_MERGE)
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
        self.work_dir = os.getcwd().replace("\\", "/")

        self._log.extra_info(f"Scanning config files, work dir: {self.work_dir}")

        config_files = []
        path_parts = self._split_path(self.work_dir)
        for i in range(1, len(path_parts) + 1):
            path = os.path.join(*path_parts[:i], self._config_file_name).replace("\\", "/")
            if os.path.isfile(path):
                self._log.debug(f"Found config file: {path}")
                config_files.append(path)

        if not config_files:
            raise ConfigError("No config files found")

        self.base_dir = os.path.dirname(config_files[0])
        self._log.debug(f"Base dir: {self.base_dir}")

        common_prefix = os.path.commonprefix([self.work_dir, self.base_dir])
        self.work_dir_rel = os.path.relpath(self.work_dir, common_prefix).replace("\\", "/")
        self._log.debug(f"Relative work dir: {self.work_dir_rel}")

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
