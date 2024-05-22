import click
from flask import current_app
from flask.cli import FlaskGroup, run_command
from wx_bot import create_app


def create(group):
    app = current_app or create_app()
    group.app = app
    return app


@click.group(cls=FlaskGroup, create_app=create)
def manager():
    pass


manager.add_command(run_command, 'runserver')