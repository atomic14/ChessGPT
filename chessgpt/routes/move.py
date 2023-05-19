import chess
from flask import jsonify, request
from chessgpt.authentication.authentication import check_auth

from chessgpt.game_state.game_state import (
    get_board_state,
    get_legal_move_list,
    load_board,
    save_board,
)
from chessgpt.utils.openai import get_conversation_id_hash


def try_make_move(app, game_state, move):
    legal_moves = get_legal_move_list(app.logger, game_state.board)
    # check the move is legal
    if move not in legal_moves:
        # maybe the move is not in SAN format? Let's try and convert it to SAN
        try:
            move_uci = chess.Move.from_uci(move)
            move = game_state.board.san(move_uci)
        except ValueError:
            # not a valid uci move either!
            return False
    # try again with the new SAN move
    if move in legal_moves:
        # make the move
        game_state.board.push_san(move)
        game_state.move_history.append(move)
        return True
    return False


def make_move_routes(app):
    @app.route("/api/move", methods=["POST"])
    @check_auth
    def make_move():
        conversation_id = request.headers.get("Openai-Conversation-Id")
        conversation_id_hash = get_conversation_id_hash(conversation_id)
        game_state = load_board(
            app.logger, app.dynamodb_client, app.GAMES_TABLE, conversation_id_hash
        )
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
        if try_make_move(app, game_state, move):
            save_board(
                app.logger,
                app.dynamodb_client,
                app.GAMES_TABLE,
                conversation_id_hash,
                game_state,
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
        else:
            legal_moves = get_legal_move_list(app.logger, game_state.board)
            app.logger.error(
                f"Illegal move: {move}, board: {game_state.board.fen()}, valiid moves: {legal_moves}"
            )
            board_state = get_board_state(
                app.logger,
                conversation_id_hash,
                game_state,
                request.scheme,
                request.host,
            )
            board_state["error_message"] = "Illegal move - make sure you use SAN"
            return (
                jsonify(board_state),
                400,
            )
