import sys
import click
import logging.config
from click.exceptions import ClickException, UsageError

from brock.exception import BaseBrockException
from brock import __version__
from .commands import status, login, init, start, stop, restart, exec


from brock.log import DEFAULT_LOGGING, getLogger

logging.config.dictConfig(DEFAULT_LOGGING)


@click.group(invoke_without_command=True, no_args_is_help=True)
@click.option("--version", is_flag=True, multiple=False, help="Show package version")
def cli(version):
    if version:
        print(__version__)
        raise RuntimeError()


cli.add_command(status)
cli.add_command(login)
cli.add_command(init)
cli.add_command(start)
cli.add_command(stop)
cli.add_command(restart)
cli.add_command(exec)


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    log = getLogger()

    try:
        ctx = cli.make_context("brock", args)

        with ctx:
            result = cli.invoke(ctx)

    except ClickException as ex:
        log.error(ex.message)
        exit(ex.exit_code)
    except RuntimeError as ex:
        pass  # * Exit and Abort from click
    except BaseBrockException as ex:
        if len(ex.message) > 0:
            log.error(ex.message)
        exit(ex.ERROR_CODE)
