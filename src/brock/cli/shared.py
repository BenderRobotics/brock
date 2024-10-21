import click

import brock.log as log


class State:

    def __init__(self, project):
        self.verbosity = 0
        self.no_color = False
        self.project = project


pass_state = click.make_pass_decorator(State)


def verbosity(f):

    def callback(ctx, param, value):
        if value == 0:
            log.VERBOSITY = log.INFO
        elif value == 1:
            log.VERBOSITY = log.EXTRA_INFO
        else:
            log.VERBOSITY = log.DEBUG

        state = ctx.find_object(State)
        if state:
            state.verbosity = value
            state.project.update_logger()

        return value

    return click.option(
        '-v', '--verbose', count=True, help='Set logging verbosity', expose_value=False, callback=callback
    )(f)


def no_color(f):

    def callback(ctx, param, value):
        if value:
            log.LOGGER = 'normal'

        state = ctx.find_object(State)
        if state:
            state.no_color = value
            state.project.update_logger()

        return value

    return click.option(
        '--no-color',
        is_flag=True,
        help='Disable default color output',
        multiple=False,
        expose_value=False,
        callback=callback
    )(f)


def shared_arguments(f):
    f = verbosity(f)
    f = no_color(f)

    return f
