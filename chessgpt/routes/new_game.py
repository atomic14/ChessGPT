import os
from chessgpt.authentication.authentication import check_auth
from chessgpt.game_state import GameState
from flask import jsonify, request

from chessgpt.game_state.game_state import get_board_state
from .levels import LEVELS
from chessgpt.utils import get_conversation_id_hash
import chess
import datetime


def new_game_routes(app):
    @app.route("/api/new_game", methods=["POST"])
    @check_auth
    def new_game():
        conversation_id = request.headers.get("Openai-Conversation-Id")
        conversation_id_hash = get_conversation_id_hash(conversation_id)
        data = request.get_json()
        if "assistant_color" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Missing assistant_color in request data. Please specify 'white' or 'black'",
                    }
                ),
                400,
            )
        if "elo" not in data:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Missing elo in request data. Please specify a number between 1350 and 2850",
                        "levels": LEVELS,
                    }
                ),
                400,
            )
        # check the elo is a number
        try:
            elo = int(data["elo"])
        except ValueError:
            app.logger.error("elo is not a number in request data: " + str(data["elo"]))
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid elo in request data. Please specify a number between 1350 and 2850",
                        "levels": LEVELS,
                    }
                ),
                400,
            )
        # check the elo is valid
        # cap the elo at 1350 and 2850
        elo = max(1350, min(2850, elo))
        # check the assistant_color is valid
        assistant_color = data["assistant_color"]
        if assistant_color not in ["white", "black"]:
            app.logger.error(
                "Invalid assistant_color in request data: " + assistant_color
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid assistant_color in request data. Please specify 'white' or 'black'",
                    }
                ),
                400,
            )
        # blank board
        board = chess.Board()
        now = int(datetime.datetime.utcnow().timestamp())
        game_state = GameState(board, [], assistant_color, elo, now, now)
        app.database.save_game_state(conversation_id_hash, game_state)
        app.logger.info(
            f"New game started. Level {elo} assistant color {assistant_color}"
        )
        return jsonify(
            get_board_state(
                app.logger,
                conversation_id_hash,
                game_state,
                request.scheme,
                request.host,
            )
        )
