import re
from munch import Munch
from typing import Dict, List, Optional

from brock.log import get_logger
from brock.exception import ConfigError, UsageError
from brock.config.config import Config
from brock.executors import Executor
from brock.executors.host import HostExecutor
from brock.executors.docker import DockerExecutor
from brock.executors.ssh import SshExecutor


class Command:
    '''Handles user defined commands

    This class provides storage for all the config options related to user
    defined commands and provides a way to execute all the defined steps with
    a correct content.
    '''

    def __init__(self, name: str, config: Munch, default_executor: Optional[str]):
        self._log = get_logger()

        self._chdir = config.get('chdir', None)
        self._depends_on = config.get('depends_on', [])
        self._default_executor = config.get('default_executor', default_executor)

        self.name = name
        self.help = config.get('help', '')

        steps = []
        for step in config.get('steps', []):
            if isinstance(step, Munch):
                steps.append(step.toDict())
            else:
                steps.append(step)
        self._steps = steps

    def exec(self, project) -> int:
        for dependency in self._depends_on:
            exit_code = project.exec(dependency)
            if exit_code != 0:
                return exit_code

        self._log.extra_info(f'Executing command {self.name}')

        for step in self._steps:
            exit_code = self._exec_step(project, step)

            if exit_code != 0:
                return exit_code

        return exit_code

    def _exec_step(self, project, step) -> int:
        if type(step) is str:
            res = re.search(r'(?:^@(\w+) )?(.*)', step)
            if res is None:
                raise ConfigError(f'Unknown step format: {step}')

            executor = res.group(1)
            command = res.group(2)
            if not executor:
                executor = self._default_executor
        elif type(step) is dict:
            executor = step.get('executor', self._default_executor)
            shell = step.get('shell', project.get_default_shell(executor))
            if shell is None:
                raise ConfigError('Shell must be specified')
            command = self._get_shell_command(step.get('script'), shell)
        else:
            raise ConfigError(f'Unexpected step type: {type(step)}')

        return project.exec_raw(command, executor, self._chdir)

    def _get_shell_command(self, script, shell) -> List[str]:
        if shell in ('sh', 'bash', 'zsh', 'powershell'):
            command = [shell, '-c']
            separator = '; '
        elif shell == 'powershell':
            command = [shell, '-Command']
            separator = '; '
        elif shell == 'cmd':
            command = [shell, '/C']
            separator = ' & '
        else:
            raise ConfigError(f'Unsupported shell: {shell}')

        lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
        command.append(separator.join(lines))

        return command


class Project:
    '''Handles processing of the cli commands related to the project configuration.'''
    _default_executor: Optional[str] = None
    _executors: Dict[str, Executor] = {}
    _commands: Dict[str, Command] = {}
    _default_command: Optional[str] = None
    _prev_executor = None

    def __init__(self, config: Config):
        executors = config.get('executors', {})
        self._log = get_logger()
        self._default_executor = executors.get('default', None)

        commands = config.get('commands', {})
        for name, cmd in commands.items():
            if name == 'default':
                self._default_command = cmd
                continue
            if len(name.split()) != 1:
                raise ConfigError(f'Command must be a single word: {name}')
            self._commands[name] = Command(name, cmd, self._default_executor)

        if self._default_command is None:
            if len(commands) == 1:
                self._default_command = next(iter(commands))

        self._executors['host'] = HostExecutor(config, 'host')
        for name, executor in executors.items():
            if name == 'default':
                continue
            elif executor.type == 'docker':
                self._executors[name] = DockerExecutor(config, name)
            elif executor.type == 'ssh':
                self._executors[name] = SshExecutor(config, name)
            else:
                raise ConfigError(f"Unknown executor type '{executor.type}'")

        if self._default_executor is None:
            if len(executors) == 0:
                self._default_executor = 'host'
            elif len(executors) == 1:
                self._default_executor = next(iter(executors))
            else:
                self._default_executor = None

    def _get_selected_executors(self, executor_name: Optional[str] = None) -> List[Executor]:
        if executor_name is not None:
            if executor_name not in self._executors:
                raise ConfigError(f'Unknown executor {executor_name}')
            return [self._executors[executor_name]]
        return list(self._executors.values())

    def on_exit(self):
        if self._prev_executor:
            self._executors[self._prev_executor].sync_out()

    @property
    def commands(self) -> Dict[str, Command]:
        return self._commands

    @property
    def default_command(self) -> Optional[str]:
        return self._default_command

    @property
    def executors(self) -> Dict[str, Executor]:
        return self._executors

    @property
    def default_executor(self) -> Optional[str]:
        return self._default_executor

    def get_default_shell(self, executor) -> Optional[str]:
        if executor in self._executors:
            return self._executors[executor].default_shell
        else:
            return None

    def status(self):
        for name, executor in self._executors.items():
            if name != 'host':
                print(f'{name}: {executor.status()}')

    def stop(self, executor_name: Optional[str] = None):
        for executor in self._get_selected_executors(executor_name):
            executor.stop()

    def restart(self, executor_name: Optional[str] = None):
        for executor in self._get_selected_executors(executor_name):
            executor.restart()

    def update(self, executor_name: Optional[str] = None):
        for executor in self._get_selected_executors(executor_name):
            executor.update()

    def exec(self, command: Optional[str] = None) -> int:
        if command is None:
            if self._default_command is None:
                raise UsageError('No default command defined')
            command = self._default_command
            self._log.info(f'No command specified, using default ({command})')

        if command not in self._commands:
            raise UsageError(f'Unknown command {command}')
        return self._commands[command].exec(self)

    def exec_raw(self, command: str, executor_name: Optional[str] = None, chdir: Optional[str] = None) -> int:
        if not executor_name:
            if self._default_executor:
                executor_name = self._default_executor
            else:
                raise ConfigError('No default executor is set!')
        if executor_name not in self._executors:
            raise ConfigError(f'Unknown executor {executor_name}')

        if self._prev_executor != executor_name:
            if self._prev_executor:
                self._executors[self._prev_executor].sync_out()
            self._executors[executor_name].sync_in()
            self._prev_executor = executor_name
        return self._executors[executor_name].exec(command, chdir)

    def shell(self, executor_name: str) -> int:
        if executor_name not in self._executors:
            raise ConfigError(f'Unknown executor {executor_name}')

        self._executors[executor_name].sync_in()
        self._prev_executor = executor_name
        return self._executors[executor_name].shell()
