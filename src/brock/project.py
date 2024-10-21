import re
from munch import Munch
from typing import Dict, List, Optional

from brock.exception import ConfigError, ExecutorError, UsageError
from brock.config.config import Config
from brock.executors import Executor
from brock.executors.shell import ShellExecutor
from brock.executors.docker import DockerExecutor
from brock.executors.ssh import SshExecutor


class Command:
    '''Handles user defined commands

    This class provides storage for all the config options related to user
    defined commands and provides a way to execute all the defined steps with
    a correct content.
    '''

    def __init__(self, config: Munch):
        self._steps = config.get('steps', [])
        self._chdir = config.get('chdir', None)
        self._depends_on = config.get('depends_on', [])
        self._default_executor = config.get('default_executor', None)
        self.help = config.get('help', '')

    def exec(self, project) -> int:
        for dependency in self._depends_on:
            exit_code = project.exec(dependency)
            if exit_code != 0:
                return exit_code

        for step in self._steps:
            res = re.search(r'(?:^@(\w+) )?(.*)', step)
            if res is None:
                raise ConfigError(f'Unknown step format: {step}')

            executor_name = res.group(1)
            command = res.group(2)
            if not executor_name:
                executor_name = self._default_executor

            exit_code = project.exec_raw(command, executor_name, self._chdir)
            if exit_code != 0:
                return exit_code

        return exit_code


class Project:
    '''Handles processing of the cli commands related to the project configuration.'''
    _default_executor: Optional[str] = None
    _executors: Dict[str, Executor] = {}
    _commands: Dict[str, Command] = {}
    _default_command: Optional[str] = None

    def __init__(self, config: Config):
        self._default_executor = config.executors.get('default', None)

        commands = config.get('commands', {})
        for name, cmd in commands.items():
            if name == 'default':
                self._default_command = cmd
                continue
            if len(name.split()) != 1:
                raise ConfigError(f'Command must be a single word: {name}')
            self._commands[name] = Command(cmd)

        self._executors['host'] = ShellExecutor(Config, 'shell', 'Execute command on host computer')
        for name, executor in config.executors.items():
            if name == 'default':
                continue
            elif executor.type == 'docker':
                self._executors[name] = DockerExecutor(config, name, executor.get('help'))
            elif executor.type == 'ssh':
                self._executors[name] = SshExecutor(config, name, executor.get('help'))
            else:
                raise ConfigError(f"Unknown executor type '{executor.type}'")

    def on_exit(self):
        for executor in self._executors.values():
            executor.on_exit()

    def update_logger(self):
        for executor in self._executors.values():
            executor.update_logger()

    def get_commands(self) -> Dict[str, Command]:
        return self._commands

    def get_executors(self) -> Dict[str, Executor]:
        return self._executors

    def get_default_executor(self) -> Optional[str]:
        if self._default_executor:
            return self._default_executor
        if len(self._executors) == 1:
            return list(self._executors.keys())[0]
        return None

    def status(self):
        for name, executor in self._executors.items():
            if name != 'host':
                print(f'{name}: {executor.status()}')

    def stop(self, executor_name: Optional[str] = None):
        if executor_name is not None:
            if executor_name not in self._executors:
                raise ConfigError(f'Unknown executor {executor_name}')
            self._executors[executor_name].stop()
            return

        for executor in self._executors.values():
            executor.stop()

    def restart(self, executor_name: Optional[str] = None):
        if executor_name is not None:
            if executor_name not in self._executors:
                raise ConfigError(f'Unknown executor {executor_name}')
            self._executors[executor_name].restart()
            return

        for executor in self._executors.values():
            executor.restart()

    def exec(self, command: Optional[str] = None) -> int:
        if command is None:
            if self._default_command is None:
                raise UsageError('No default command defined')
            command = self._default_command

        if command not in self._commands:
            raise UsageError(f'Unknown command {command}')
        return self._commands[command].exec(self)

    def exec_raw(self, command: str, executor_name: Optional[str] = None, chdir: Optional[str] = None) -> int:
        if not executor_name:
            # raw execution uses host executor if no other specified
            if self._default_executor:
                executor_name = self._default_executor
            else:
                executor_name = 'host'
        if executor_name not in self._executors:
            raise ConfigError(f'Unknown executor {executor_name}')
        return self._executors[executor_name].exec(command, chdir)

    def shell(self, executor_name: str) -> int:
        if executor_name not in self._executors:
            raise ConfigError(f'Unknown executor {executor_name}')
        return self._executors[executor_name].shell()
