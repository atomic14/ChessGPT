from app import app
from flask import jsonify, request
from chessgpt.game_state.game_state import load_board

from chessgpt.utils.openai import get_conversation_id_hash


@app.route("/api/fen", methods=["GET"])
def get_fen():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    game_state = load_board(conversation_id_hash)
    if not game_state:
        app.logger.error("No game found for conversation ID: " + conversation_id)
        return jsonify({"success": False, "message": "No game found"}), 404
    return jsonify({"FEN": game_state.board.fen()})
