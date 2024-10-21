import click

from brock.log import getLogger
from brock.exception import UsageError
from brock.config.config import Config
from .shared import shared_arguments, pass_state


@click.command()
@shared_arguments
@pass_state
def init(state):
    log = getLogger()

    log.info(f"Initializing toolchain")

    config = Config()

@click.command()
@shared_arguments
@pass_state
def start(state):
    log = getLogger()

    log.info(f"Starting toolchain")

    config = Config()

@click.command()
@shared_arguments
@pass_state
def stop(state):
    log = getLogger()

    log.info(f"Stopping toolchain")

    config = Config()

@click.command(context_settings=dict(
    ignore_unknown_options=True,
    allow_extra_args=True,
))
@click.pass_context
@shared_arguments
@pass_state
def run(state, ctx):
    log = getLogger()

    log.info(f"Running toolchain")

    config = Config()

    if ctx.args:
        cmd = ' '.join(ctx.args)
    else:
        try:
            cmd = config.toolchain.default_cmd
        except AttributeError:
            raise UsageError("Command not specified")

    log.debug(f"Command: {cmd}")
