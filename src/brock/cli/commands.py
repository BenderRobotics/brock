import click

from brock.log import getLogger
from brock.exception import ConfigError, UsageError
from brock.config.config import Config
from brock.toolchain.toolchain import Toolchain
from .shared import shared_arguments, pass_state


@click.command()
@shared_arguments
@pass_state
def status(state):
    log = getLogger()
    config = Config()

    log.info(f"Toolchain status:")

    toolchain = Toolchain(config)
    toolchain.get_state()

@click.command()
@shared_arguments
@pass_state
def init(state):
    log = getLogger()
    config = Config()

    log.info(f"Initializing toolchain")

    toolchain = Toolchain(config)
    toolchain.pull()

@click.command()
@shared_arguments
@pass_state
def start(state):
    log = getLogger()
    config = Config()

    log.info(f"Starting toolchain")

    toolchain = Toolchain(config)
    toolchain.start()

@click.command()
@shared_arguments
@pass_state
def stop(state):
    log = getLogger()
    config = Config()

    log.info(f"Stopping toolchain")

    toolchain = Toolchain(config)
    toolchain.stop()

@click.command()
@shared_arguments
@pass_state
def restart(state):
    log = getLogger()
    config = Config()

    log.info(f"Restarting toolchain")

    toolchain = Toolchain(config)
    toolchain.stop()
    toolchain.start()

@click.command(context_settings=dict(
    ignore_unknown_options=True,
    allow_extra_args=True,
))
@click.pass_context
@shared_arguments
@pass_state
def exec(state, ctx):
    log = getLogger()
    config = Config()

    if ctx.args:
        cmd = ' '.join(ctx.args)
    else:
        try:
            cmd = config.toolchain.default_cmd
        except AttributeError:
            raise UsageError("Command not specified")

    log.info(f"Executing command")

    toolchain = Toolchain(config)
    toolchain.exec(cmd)
