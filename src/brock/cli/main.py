import sys
import click
import collections
import logging.config
from munch import Munch
from typing import Dict, Tuple
from click.exceptions import ClickException
from .shared import shared_arguments, State, pass_state

from brock.exception import BaseBrockException, ConfigError, UsageError
from brock.project import Project
from brock.config.config import Config
from brock import __version__
from brock.log import DEFAULT_LOGGING, getLogger
from .commands import create_command, shell, exec

logging.config.dictConfig(DEFAULT_LOGGING)


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
@click.pass_context
@shared_arguments
def cli(ctx, stop, update, restart, status):
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

    log = getLogger()
    project = None
    exit_code = 0

    try:
        config_error = None
        try:
            config = Config()
        except ConfigError as e:
            config = Munch()
            config_error = e

        project = Project(config)
        state = State(project)
        state.error = config_error

        cli.add_command(shell)
        cli.add_command(exec)

        for name, cmd in project.get_commands().items():
            cli.add_command(create_command(name, cmd.help))
        cli.help = config.get('help', '')

        executors = []
        for name, executor in project.get_executors().items():
            executors.append((name, executor.help or ''))
        cli.custom_epilog = {'Executors': executors}

        ctx = cli.make_context('brock', args)
        ctx.obj = state

        with ctx:
            result = cli.invoke(ctx)
            if result is not None:
                exit_code = result
    except ClickException as ex:
        log.error(ex.message)
        exit_code = ex.exit_code
    except RuntimeError as ex:
        pass  # * Exit and Abort from click
    except BaseBrockException as ex:
        if len(ex.message) > 0:
            log.error(ex.message)
        exit_code = ex.ERROR_CODE

    if project:
        project.on_exit()
    exit(exit_code)
