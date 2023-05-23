import chess.svg
from flask import jsonify, request, Response

from chessgpt.compression.huffman import decode_board


def board_routes(app):
    @app.route("/board.svg", methods=["GET"])
    def board():
        # log the referrer
        app.logger.info(f"Referrer: {request.referrer}")
        # do we have the b parameter?
        b = request.args.get("b")
        if b is None:
            # do we have a fen parameter?
            fen = request.args.get("fen")
            if fen is not None:
                app.logger.info(f"Decoding board from fen {fen}")
                try:
                    # replace any + with ' '
                    fen = fen.replace("+", " ")
                    board = chess.Board(fen)
                    svg_data = chess.svg.board(board=board, size=400)
                    response = Response(svg_data, mimetype="image/svg+xml")
                    response.headers["Cache-Control"] = "public, max-age=31536000"
                    return response
                except ValueError:
                    app.logger.error("Invalid fen query parameter")
                    return (
                        jsonify(
                            {"success": False, "message": "Invalid fen query parameter"}
                        ),
                        400,
                    )
            app.logger.error("Missing b query parameter")
            return (
                jsonify({"success": False, "message": "Missing b query parameter"}),
                400,
            )
        app.logger.info(f"Decoding board from query param {b}")
        try:
            board = decode_board(b)
            svg_data = chess.svg.board(board=board, size=400)
            response = Response(svg_data, mimetype="image/svg+xml")
            response.headers["Cache-Control"] = "public, max-age=31536000"
            return response
        except ValueError:
            app.logger.error("Invalid b query parameter")
            return (
                jsonify({"success": False, "message": "Invalid b query parameter"}),
                400,
            )
