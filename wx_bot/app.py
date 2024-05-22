from flask import Flask

class WXBOT(Flask):
    def __init__(self, *args, **kwargs):
        super(WXBOT, self).__init__(__name__, *args, **kwargs)
        self.config.from_object('wx_bot.config')


def create_app():
    from . import handlers
    from .models import redis

    app = WXBOT()
    redis.init_app(app)
    handlers.init_app(app)
    return app
