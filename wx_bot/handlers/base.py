from flask_restful import Resource

from flask import Blueprint

routes = Blueprint('wxbot', __name__)

class BaseResource(Resource):
    def __init__(self, *args, **kwargs):
        super(BaseResource, self).__init__(*args, **kwargs)
