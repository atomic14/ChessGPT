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
def save_board(conversation_id_hash, move_history, assistant_color):
    dynamodb_client.put_item(
        TableName=GAMES_TABLE,
        Item={
            "conversationId": conversation_id_hash,
            "moves": ",".join(move_history),
            "assistant_color": assistant_color,
        },
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
        return None, None, None

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
    assistant_color = item.get("assistant_color")
    return board, moves, assistant_color


# get the list of legan moves in SAN format
def get_legal_move_list(board):
    legal_moves = [board.san(move) for move in board.legal_moves]
    return legal_moves


def get_markdown(conversation_id_hash, move_history):
    # create an MD5 hash of the board FEN
    # this will be used to bust the browser cache
    markdown = f"![Board]({request.scheme}://{request.host}/board.svg?cid={conversation_id_hash}&m={len(move_history)})"
    return markdown


def get_board_state(conversation_id_hash, board, move_history, assistant_color):
    # work out who's turn is it from the move_history
    if len(move_history) % 2 == 0:
        turn = "white"
    else:
        turn = "black"
    # pair the moves from white and black
    moves_string = ""
    for i in range(0, len(move_history), 2):
        if i + 1 < len(move_history):
            moves_string += f"{int(i/2 + 1)}. {move_history[i]} {move_history[i + 1]} "
        else:
            moves_string += f"{int(i/2 + 1)}. {move_history[i]} "
    moves_string = moves_string.strip()
    # create the instructions for the assistant
    if turn == assistant_color:
        instructions = (
            "It's the assistant's turn. Use the FEN to determine the location of the pieces. Select the best move for the assistant making sure you avoid blundering pieces and making mistakes."
            + "Pay close attention to the position of the pieces on the board. Anlyze the position and make the best move for the assistant. "
            + "Use the make move API to make the move for the assistant and the show the board to the user using the markdown from the display field."
        )
    else:
        instructions = (
            "It's the user's turn to move. Show the board to the user using the markdown from the display field. Prompt the user to make their move using SAN notation"
            + " (e.g. e4, Nf3, etc). Use the make move API to make the move for the user and the show the board to the user using the markdown from the display field."
        )

    return {
        "move_history": moves_string,
        "FEN": board.fen(),
        "game_over": board.is_game_over(),
        "display": get_markdown(conversation_id_hash, move_history),
        "EXTRA_INFORMATION_TO_ASSISTANT": instructions,
    }


@app.route("/api/new_game", methods=["POST"])
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
    assistant_color = data["assistant_color"]
    if assistant_color not in ["white", "black"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid assistant_color in request data. Please specify 'white' or 'black'",
                }
            ),
            400,
        )
    # no moves yet
    save_board(conversation_id_hash, [], assistant_color)
    # blank board
    board = chess.Board()
    logging.debug("New game started.")
    return jsonify(get_board_state(conversation_id_hash, board, [], assistant_color))


@app.route("/api/move", methods=["POST"])
def make_move():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    board, move_history, assistant_color = load_board(conversation_id_hash)
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
            save_board(conversation_id_hash, move_history, assistant_color)
            return jsonify(
                get_board_state(
                    conversation_id_hash, board, move_history, assistant_color
                )
            )
        else:
            logging.error("Illegal move: " + move)
            board_state = get_board_state(
                conversation_id_hash, board, move_history, assistant_color
            )
            board_state["error_message"] = "Illegal move - make sure you use SAN"
            return (
                jsonify(board_state),
                400,
            )
    except ValueError as e:
        logging.error("Invalid move format: " + move)
        logging.error(e)
        board_state = get_board_state(
            conversation_id_hash, board, move_history, assistant_color
        )
        board_state["error_message"] = "Invalid move format - use SAN"
        return (
            jsonify(board_state),
            400,
        )


@app.route("/board.svg", methods=["GET"])
def board():
    # get the query param cid - this is the conversation ID
    conversation_id_hash = request.args.get("cid")
    move = request.args.get("m")
    move = int(move)
    board, _, _ = load_board(conversation_id_hash, move)

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
        data = data.replace("PROTOCOL", request.scheme)
        # return the modified file
        return Response(data, mimetype="application/json")


@app.route("/openapi.yaml")
def serve_openai_yaml():
    # read in the file
    with open("openapi.yaml", "r") as f:
        data = f.read()
        # replace the string PLUGIN_HOSTNAME with the actual hostname
        data = data.replace("PLUGIN_HOSTNAME", request.host)
        data = data.replace("PROTOCOL", request.scheme)
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
