import click

import brock.log as log


class State:
    def __init__(self):
        self.verbosity = 0
        self.no_color = False


pass_state = click.make_pass_decorator(State, ensure=True)


def verbosity(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.verbosity = value

        if value == 0:
            log.VERBOSITY = log.INFO
        elif value == 1:
            log.VERBOSITY = log.EXTRA_INFO
        else:
            log.VERBOSITY = log.DEBUG

        return value

    return click.option(
        '-v', '--verbose', count=True, help="Set logging verbosity",
        expose_value=False, callback=callback
    )(f)


def no_color(f):
    def callback(ctx, param, value):
        state = ctx.ensure_object(State)
        state.no_color = value

        if value:
            log.LOGGER = 'normal'

        return value

    return click.option(
        '--no-color', is_flag=True, help="Disable default color output",
        multiple=False, expose_value=False, callback=callback
    )(f)


def shared_arguments(f):
    f = verbosity(f)
    f = no_color(f)

    return f
