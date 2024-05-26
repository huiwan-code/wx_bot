from wx_bot.handlers.api import api
from wx_bot.handlers.base import routes


def init_app(app):
    api.init_app(app)
    app.register_blueprint(routes)
