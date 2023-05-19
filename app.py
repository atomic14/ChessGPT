import os
from flask import Flask, jsonify, make_response
from flask_cors import CORS
from chessgpt.routes import (
    board_routes,
    get_fen_routes,
    get_levels_routes,
    get_move_history_routes,
    make_move_routes,
    new_game_routes,
    static_routes,
)
from chessgpt.logging.logging import setup_logging
from chessgpt.database.dynamodb import Database

app = Flask(__name__)
CORS(app)


setup_logging(app)

app.database = Database(app.logger)

# register routes
board_routes(app)
get_fen_routes(app)
get_levels_routes(app)
get_move_history_routes(app)
make_move_routes(app)
new_game_routes(app)
static_routes(app)

app.logger.info("Starting app")


@app.errorhandler(404)
def resource_not_found(e):
    return make_response(jsonify(error="Not found!"), 404)


@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(e)
    return make_response(jsonify(error="Internal Server Error!"), 500)
