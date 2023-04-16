import os
import boto3
from flask import Flask, jsonify, make_response, request, send_from_directory, Response
import chess
import chess.svg
import chess.pgn
import logging
import hashlib
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)


if os.environ.get("IS_OFFLINE") == "True":
    print("Running in offline mode")
    session = boto3.Session(aws_access_key_id="DUMMY", aws_secret_access_key="DUMMY")
    dynamodb_client = session.resource(
        "dynamodb", region_name="localhost", endpoint_url="http://localhost:8000"
    ).meta.client
else:
    session = boto3.Session()
    dynamodb_client = session.resource("dynamodb").meta.client


GAMES_TABLE = os.environ["GAMES_TABLE"]


def get_conversation_id_hash(conversation_id):
    return hashlib.md5(conversation_id.encode("utf-8")).hexdigest()


# save the board state to dynamoDB - we'll just save the move history
def save_board(conversation_id_hash, move_history):
    logging.debug(
        "****** Saving board state to table:"
        + GAMES_TABLE
        + " for conversation: "
        + conversation_id_hash
    )
    dynamodb_client.put_item(
        TableName=GAMES_TABLE,
        Item={"conversationId": conversation_id_hash, "moves": ",".join(move_history)},
    )


# load the board up from dynamoDB - we'll get the move history and then
# replay the moves to get the board state
def load_board(conversation_id_hash, max_move=None):
    result = dynamodb_client.get_item(
        TableName=GAMES_TABLE, Key={"conversationId": conversation_id_hash}
    )
    item = result.get("Item")
    if not item:
        logging.error("No game found for conversation: " + conversation_id_hash)
        return None, None

    moves_string = item.get("moves")
    if not moves_string:
        moves = []
    else:
        moves = moves_string.split(",")
    logging.debug("Moves: " + str(moves))
    board = chess.Board()
    if max_move is None:
        max_move = len(moves)
    print("Max move: " + str(max_move))
    for move in moves[:max_move]:
        board.push_san(move)
    return board, moves


# get the list of legan moves in SAN format
def get_legal_move_list(board):
    legal_moves = [board.san(move) for move in board.legal_moves]
    return legal_moves


def get_markdown(conversation_id_hash, board, move_history):
    # create an MD5 hash of the board FEN
    # this will be used to bust the browser cache
    markdown = f"![Board](https://{request.host}/board.svg?cid={conversation_id_hash}&m={len(move_history)})"
    return markdown


def get_board_state(host, conversation_id_hash, board, move_history):
    # work out who's turn is it from the move_history
    if len(move_history) % 2 == 0:
        turn = "White"
    else:
        turn = "Black"
    # get the positions of the pieces
    piece_map = board.piece_map()
    # list all the pieces and their positions
    pieces = [
        {"piece": pieces.symbol(), "square": chess.SQUARE_NAMES[square - 1]}
        for square, pieces in piece_map.items()
    ]
    # pair the moves from white and black
    moves_string = ""
    for i in range(0, len(move_history), 2):
        if i + 1 < len(move_history):
            moves_string += f"{int(i/2 + 1)}. {move_history[i]} {move_history[i + 1]} "
        else:
            moves_string += f"{int(i/2 + 1)}. {move_history[i]} "
    moves_string = moves_string.strip()

    return {
        "move_history": moves_string,
        # "fen": board.fen(),
        "pieces": pieces,
        "game_over": board.is_game_over(),
        "nextPlayer": turn,
        "display": get_markdown(conversation_id_hash, board, move_history),
        "instructions": "Show the board to the user",
        "EXTRA_INFORMATION_TO_ASSISTANT": "Use the move_histroy to work out the best move for the assistant. If it is your turn, make your move. Show the user the board after your turn using the markdown from the display property.",
    }


@app.route("/api/new_game", methods=["POST"])
def new_game():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    # no moves yet
    save_board(conversation_id_hash, [])
    # blank board
    board = chess.Board()
    logging.debug("New game started.")
    return jsonify(get_board_state(request.host, conversation_id_hash, board, []))


@app.route("/api/move", methods=["POST"])
def make_move():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    board, move_history = load_board(conversation_id_hash)
    if not board:
        return jsonify({"success": False, "message": "No game found"}), 404

    data = request.get_json()

    if "move" not in data:
        return (
            jsonify({"success": False, "message": "Missing move in request data"}),
            400,
        )

    move = data["move"]
    try:
        if move in get_legal_move_list(board):
            board.push_san(move)
            move_history.append(move)
            save_board(conversation_id_hash, move_history)
            return jsonify(
                get_board_state(request.host, conversation_id_hash, board, move_history)
            )
        else:
            logging.error("Illegal move: " + move)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Illegal move - make sure you use SAN",
                    }
                ),
                400,
            )
    except ValueError as e:
        logging.error("Invalid move format: " + move)
        logging.error(e)
        return (
            jsonify({"success": False, "message": "Invalid move format - use SAN"}),
            400,
        )


@app.route("/board.svg", methods=["GET"])
def board():
    # get the query param cid - this is the conversation ID
    conversation_id_hash = request.args.get("cid")
    move = request.args.get("m")
    move = int(move)
    board, move_history = load_board(conversation_id_hash, move)

    svg_data = chess.svg.board(board=board, size=400)
    response = Response(svg_data, mimetype="image/svg+xml")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/.well-known/ai-plugin.json")
def serve_ai_plugin():
    # read in the file
    with open(".well-known/ai-plugin.json", "r") as f:
        data = f.read()
        # replace the string PLUGIN_HOSTNAME with the actual hostname
        data = data.replace("PLUGIN_HOSTNAME", request.host)
        # return the modified file
        return Response(data, mimetype="application/json")


@app.route("/openapi.yaml")
def serve_openai_yaml():
    # read in the file
    with open("openapi.yaml", "r") as f:
        data = f.read()
        # replace the string PLUGIN_HOSTNAME with the actual hostname
        data = data.replace("PLUGIN_HOSTNAME", request.host)
        # return the modified file
        return Response(data, mimetype="text/yaml")


@app.route("/logo.png")
def serve_logo():
    # cache for 24 hours
    response = send_from_directory(".", "logo.png")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/robots.txt")
def serve_robots():
    # cache for 24 hours
    response = send_from_directory(".", "robots.txt")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.errorhandler(404)
def resource_not_found(e):
    return make_response(jsonify(error="Not found!"), 404)
