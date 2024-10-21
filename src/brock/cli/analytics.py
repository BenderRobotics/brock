import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

import brock

trace = sentry_sdk.trace
breadcrumb = sentry_sdk.add_breadcrumb


def trace_entry(func):

    def wrapper(*args, **kwargs):
        with sentry_sdk.start_transaction(op=func.__name__, name=func.__name__):
            return func(*args, **kwargs)

    return wrapper


def init_analytics(enable_dev_analytics: bool) -> None:
    env = 'devel' if enable_dev_analytics else 'main'
    release = None if enable_dev_analytics else brock.__version__
    sentry_sdk.init(
        # This is a public information
        dsn='https://75fe6c1dbd9ffcffebc2a9df1bf793cd@sentry.benderrobotics.com/4',
        environment=env,
        release=release,
        include_local_variables=True,
        before_send=_before_send,
        debug=False,
        integrations=[
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.CRITICAL  # Send records as events
            )
        ]
    )


def _before_send(event, hint):
    if 'exc_info' in hint:
        _, exc_value, tb = hint['exc_info']
        if isinstance(exc_value, KeyboardInterrupt):
            return None

    return event
