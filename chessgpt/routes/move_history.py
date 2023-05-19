from flask import jsonify, request
from chessgpt.authentication.authentication import check_auth
from chessgpt.game_state.game_state import format_moves, load_board

from chessgpt.utils.openai import get_conversation_id_hash


def get_move_history(app):
    @app.route("/api/move_history", methods=["GET"])
    @check_auth
    def get_move_history():
        conversation_id = request.headers.get("Openai-Conversation-Id")
        conversation_id_hash = get_conversation_id_hash(conversation_id)
        game_state = load_board(
            app.logger, app.dynamodb_client, app.GAMES_TABLE, conversation_id_hash
        )
        if not game_state:
            app.logger.error(f"No game found for conversation ID: {conversation_id}")
            return jsonify({"success": False, "message": "No game found"}), 404
        moves = format_moves(app.logger, game_state.move_history)
        return jsonify({"move_history": moves})
