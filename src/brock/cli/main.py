import sys
import click
import collections
import logging.config
from typing import Dict, Tuple
from click.exceptions import ClickException
from .state import State, set_verbosity, set_no_color, set_analytics, set_analytics_dev

from brock.exception import BaseBrockException, ConfigError, UsageError
from brock.project import Project
from brock.config.config import Config
from brock import __version__
from brock.log import get_logger, init_logging
from .commands import create_command, shell, exec, create_command_with_options


class CustomCommandGroup(click.Group):
    '''Custom click group for customized help formatting

    The epilog is replaces with custom_epilog with commands like formatting
    with multiple sections possible (e.g. {'Executors': [('python', 'help msg')]})

    The commands are listed in order in they were added
    '''
    custom_epilog: Dict[str, Tuple[str, str]] = {}

    def __init__(self, name=None, commands=None, **attrs):
        super(CustomCommandGroup, self).__init__(name, commands, **attrs)
        #: the registered subcommands by their exported names.
        self.commands = commands or collections.OrderedDict()

    def format_epilog(self, ctx, formatter):
        for section, content in self.custom_epilog.items():
            with formatter.section(section):
                formatter.write_dl(content)

    def list_commands(self, ctx):
        return self.commands


def analytics_options_decorator(func):
    if 'dev' not in __version__:
        return click.option(
            '--disable-analytics',
            is_flag=True,
            expose_value=False,
            default=False,
            callback=set_analytics,
            help='Disable analytics features.'
        )(func)
    else:
        return click.option(
            '--enable-dev-analytics',
            is_flag=True,
            expose_value=False,
            default=False,
            callback=set_analytics_dev,
            help='Force enable analytics during development.'
        )(func)


@click.group(cls=CustomCommandGroup, invoke_without_command=True)
@click.version_option(__version__)
@click.option('--stop', is_flag=False, flag_value='all', default=None, help='Stop project', metavar='[EXECUTOR]')
@click.option(
    '--update',
    is_flag=False,
    flag_value='all',
    default=None,
    help='Update the executor (pull docker image, ...)',
    metavar='[EXECUTOR]'
)
@click.option(
    '-r',
    '--restart',
    is_flag=False,
    flag_value='all',
    default=None,
    help='Restart project (e.g. to reload config)',
    metavar='[EXECUTOR]'
)
@click.option('-s', '--status', is_flag=True, help='Show state of the project')
@click.option('-v', '--verbose', count=True, help='Set logging verbosity', expose_value=False, callback=set_verbosity)
@click.option(
    '--no-color',
    is_flag=True,
    help='Disable default color output',
    multiple=False,
    expose_value=False,
    callback=set_no_color
)
@analytics_options_decorator
@click.pass_context
def cli(ctx, stop, update, restart, status, **kwargs):
    state = ctx.find_object(State)
    # allow running --help and --version even if config parsing failed
    if state.error:
        raise state.error

    if ctx.invoked_subcommand is None:
        if stop:
            ctx.obj.project.stop(None if stop == 'all' else stop)
        elif update:
            ctx.obj.project.update(None if update == 'all' else update)
        elif restart:
            ctx.obj.project.restart(None if restart == 'all' else restart)
        elif status:
            ctx.obj.project.status()
        else:
            # default command if available
            state.project.exec()
    elif stop or update or restart or status:
        raise UsageError('Invalid arguments combination')


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    init_logging()
    log = get_logger()
    project = None
    exit_code = 0

    try:
        config_error = None
        try:
            config = Config()
            project = Project(config)
        except ConfigError as e:
            config_error = e

        state = State(project)
        state.error = config_error

        cli.add_command(shell)
        cli.add_command(exec)

        if project:
            for name, cmd in project.commands.items():
                help = cmd.help + (' (default)' if name == project.default_command else '')
                if cmd.options:
                    cli.add_command(create_command_with_options(name, cmd.options, help.strip()))
                else:
                    cli.add_command(create_command(name, help.strip()))
            cli.help = config.get('help', '')

            executors = []
            for name, executor in project.executors.items():
                help = executor.help + (' (default)' if name == project.default_executor else '')
                executors.append((name, help.strip()))
            cli.custom_epilog = {'Executors': executors}

        cli_error = None
        try:
            result = cli(obj=state, standalone_mode=False, args=args)
        except RuntimeError:
            # * Exit and Abort from click
            result = None
        except Exception as ex:
            cli_error = ex

        if config_error:
            raise config_error
        elif cli_error:
            raise cli_error
        elif result is not None:
            exit_code = result
    except ClickException as ex:
        log.error(ex.message)
        exit_code = ex.exit_code
    except BaseBrockException as ex:
        if len(ex.message) > 0:
            log.error(ex.message)
        exit_code = ex.ERROR_CODE

    if project:
        project.on_exit()
    exit(exit_code)
