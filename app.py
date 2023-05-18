import os
from flask import Flask, jsonify, make_response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

from chessgpt.database.dynamodb import get_dynamodb_client  # noqa
from chessgpt.logging.logging import setup_logging  # noqa

setup_logging()

app.dynamodb_client = get_dynamodb_client()

app.GAMES_TABLE = os.environ["GAMES_TABLE"]

import chessgpt.routes  # noqa

app.logger.info("Starting app")


@app.errorhandler(404)
def resource_not_found(e):
    return make_response(jsonify(error="Not found!"), 404)


@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(e)
    return make_response(jsonify(error="Internal Server Error!"), 500)
