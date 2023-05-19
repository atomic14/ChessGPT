import chess.svg
from flask import jsonify, request, Response

from chessgpt.compression.huffman import decode_board
from chessgpt.game_state.game_state import load_board


def board_routes(app):
    @app.route("/board.svg", methods=["GET"])
    def board():
        # do we have the b parameter?
        b = request.args.get("b")
        if b is not None:
            app.logger.info(f"Decoding board from query param {b}")
            board = decode_board(b)
        else:
            # get the query param cid - this is the conversation ID
            conversation_id_hash = request.args.get("cid")
            if conversation_id_hash is None:
                app.logger.error("Missing cid query parameter")
                return (
                    jsonify(
                        {"success": False, "message": "Missing cid query parameter"}
                    ),
                    400,
                )
            move = request.args.get("m")
            if move is None:
                app.logger.error("Missing m query parameter")
                return (
                    jsonify({"success": False, "message": "Missing m query parameter"}),
                    400,
                )
            # check that the move is a number
            try:
                int(move)
            except ValueError:
                app.logger.error(", is not an integer query parameter")
                return (
                    jsonify({"success": False, "message": "Invalid m query parameter"}),
                    400,
                )

            game_state = load_board(
                app.logger,
                app.dynamodb_client,
                app.GAMES_TABLE,
                conversation_id_hash,
                int(move),
            )
            if not game_state:
                app.logger.error("No game found for cid " + conversation_id_hash)
                return jsonify({"success": False, "message": "No game found"}), 404
            board = game_state.board

        svg_data = chess.svg.board(board=board, size=400)
        response = Response(svg_data, mimetype="image/svg+xml")
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response
