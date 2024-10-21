import click

from brock.log import getLogger
from .shared import shared_arguments, pass_state


@click.command()
@shared_arguments
@pass_state
def init(state):
    log = getLogger()

    log.info(f"Initializing toolchain")

@click.command()
@shared_arguments
@pass_state
def start(state):
    log = getLogger()

    log.info(f"Starting toolchain")

@click.command()
@shared_arguments
@pass_state
def stop(state):
    log = getLogger()

    log.info(f"Stopping toolchain")

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
    log.debug(f"Command: {' '.join(ctx.args)}")
