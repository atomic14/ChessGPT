from flask import jsonify, request
from app import app

from chessgpt.game_state.game_state import (
    get_board_state,
    get_legal_move_list,
    load_board,
    save_board,
)
from chessgpt.utils.openai import get_conversation_id_hash


@app.route("/api/move", methods=["POST"])
def make_move():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    game_state = load_board(conversation_id_hash)
    if not game_state:
        app.logger.error("No game found")
        return jsonify({"success": False, "message": "No game found"}), 404

    data = request.get_json()

    if "move" not in data:
        app.logger.error("Missing move in request data")
        return (
            jsonify({"success": False, "message": "Missing move in request data"}),
            400,
        )

    move = data["move"]
    # check the move is legal
    try:
        if move in get_legal_move_list(game_state.board):
            # make the move
            game_state.board.push_san(move)
            game_state.move_history.append(move)
            save_board(conversation_id_hash, game_state)
            return jsonify(
                get_board_state(
                    conversation_id_hash, game_state, request.scheme, request.host
                )
            )
        else:
            app.logger.error("Illegal move: " + move)
            board_state = get_board_state(
                conversation_id_hash, game_state, request.scheme, request.host
            )
            board_state["error_message"] = "Illegal move - make sure you use SAN"
            return (
                jsonify(board_state),
                400,
            )
    except ValueError:
        app.logger.error("Invalid move format: " + move)
        board_state = get_board_state(
            conversation_id_hash, game_state, request.scheme, request.host
        )
        board_state["error_message"] = "Invalid move format - use SAN"
        return (
            jsonify(board_state),
            400,
        )
