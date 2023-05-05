import collections
import os
import shutil
import boto3
from flask import Flask, jsonify, make_response, request, send_from_directory, Response
import chess
import chess.svg
import chess.pgn
import logging
import hashlib
from flask_cors import CORS
from stockfish import Stockfish

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.DEBUG)


# create a named tuple to hold the game state
GameState = collections.namedtuple(
    "GameState", ["board", "move_history", "assistant_color", "elo"]
)

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

LEVELS = [
    {
        "name": "Beginner",
        "elo": 1000,
        "description": "The assistant will play at an Elo rating of 1000. This is a good level for beginners.",
    },
    {
        "name": "Intermediate",
        "elo": 1500,
        "description": "The assistant will play at an Elo rating of 1500. This is a good level for intermediate players.",
    },
    {
        "name": "Advanced",
        "elo": 2000,
        "description": "The assistant will play at an Elo rating of 2000. This is a good level for advanced players.",
    },
    {
        "name": "Expert",
        "elo": 2500,
        "description": "The assistant will play at an Elo rating of 2500. This is a good level for expert players.",
    },
    {
        "name": "Grandmaster",
        "elo": 3000,
        "description": "The assistant will play at an Elo rating of 3000. This is a good level for grandmasters.",
    },
]


def get_conversation_id_hash(conversation_id):
    return hashlib.md5(conversation_id.encode("utf-8")).hexdigest()


def get_stockfish_path():
    result = shutil.which("stockfish")
    if result is None:
        # locate the binary from ./stockfish
        result = os.path.join(os.path.dirname(__file__), "stockfish/stockfish")
    return result


def get_stockfish(elo, fen):
    stockfish = Stockfish(get_stockfish_path())
    stockfish.set_elo_rating(elo)
    stockfish.set_fen_position(fen)
    return stockfish


def get_best_moves(stockfish, num=5):
    return stockfish.get_top_moves(num)


# save the board state to dynamoDB - we'll just save the move history
def save_board(conversation_id_hash: str, game_state: GameState):
    dynamodb_client.put_item(
        TableName=GAMES_TABLE,
        Item={
            "conversationId": conversation_id_hash,
            "moves": ",".join(game_state.move_history),
            "assistant_color": game_state.assistant_color,
            "elo": str(game_state.elo),
        },
    )


# load the board up from dynamoDB - we'll get the move history and then
# replay the moves to get the board state
def load_board(conversation_id_hash, max_move=None) -> GameState:
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
    elo = int(item.get("elo", "2000"))
    return GameState(board, moves, assistant_color, elo)


# get the list of legal moves in SAN format
def get_legal_move_list(board):
    legal_moves = [board.san(move) for move in board.legal_moves]
    return legal_moves


def get_markdown(conversation_id_hash, move_history):
    # create an MD5 hash of the board FEN
    # this will be used to bust the browser cache
    markdown = f"![Board]({request.scheme}://{request.host}/board.svg?cid={conversation_id_hash}&m={len(move_history)})"
    return markdown


def format_moves(move_history):
    # pair the moves from white and black
    moves = []
    for i in range(0, len(move_history), 2):
        if i + 1 < len(move_history):
            moves.append(f"{int(i/2 + 1)}. {move_history[i]} {move_history[i + 1]}")
        else:
            moves.append(f"{int(i/2 + 1)}. {move_history[i]}")
    return moves


def get_board_state(conversation_id_hash, game_state: GameState):
    # work out who's turn is it from the move_history
    if len(game_state.move_history) % 2 == 0:
        turn = "white"
    else:
        turn = "black"
    # pair the moves from white and black
    moves = format_moves(game_state.move_history)
    # get the best moves for the assistant or user (give the user grandmaster moves!)
    best_move_elo = game_state.elo if turn == game_state.assistant_color else 3000
    stockfish = get_stockfish(best_move_elo, game_state.board.fen())
    best_moves = get_best_moves(stockfish)
    # convert the best moves to SAN
    best_moves_san = [
        game_state.board.san(chess.Move.from_uci(move["Move"])) for move in best_moves
    ]
    # create the instructions for the assistant
    if turn == game_state.assistant_color:
        instructions = (
            f"It's the assistant's turn. The assistant is playing {turn}. Pick a move from the following best moves for {turn}: {', '.join(best_moves_san)}. "
            + "Use the make move API to make the move for the assistant and the show the board to the user using the markdown from the display field."
        )
    else:
        instructions = (
            f"It's the user's turn to move. The user is playing {turn}. Show the board to the user using the markdown from the display field. Prompt the user to make their move using SAN notation"
            + " (e.g. e4, Nf3, etc). Use the make move API to make the move for the user and the show the board to the user using the markdown from the display field."
        )

    return {
        "FEN": game_state.board.fen(),
        "move_history": moves,
        "game_over": game_state.board.is_game_over(),
        "display": get_markdown(conversation_id_hash, game_state.move_history),
        "best_moves": ", ".join(best_moves_san),
        "EXTRA_INFORMATION_TO_ASSISTANT": instructions,
    }


@app.route("/api/levels", methods=["GET"])
def get_levels():
    return jsonify(LEVELS)


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
    if "elo" not in data:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Missing elo in request data. Please specify a number between 1000 and 3000",
                    "levels": LEVELS,
                }
            ),
            400,
        )
    # check the elo is a number
    try:
        elo = int(data["elo"])
    except ValueError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid elo in request data. Please specify a number between 1000 and 3000",
                    "levels": LEVELS,
                }
            ),
            400,
        )
    # check the elo is valid
    if elo < 0 or elo > 3000:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Invalid elo in request data. Please specify a number between 0 and 3000",
                    "levels": LEVELS,
                }
            ),
            400,
        )
    # check the assistant_color is valid
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
    # blank board
    board = chess.Board()
    game_state = GameState(board, [], assistant_color, elo)
    save_board(conversation_id_hash, game_state)
    logging.debug("New game started.")
    return jsonify(get_board_state(conversation_id_hash, game_state))


@app.route("/api/move", methods=["POST"])
def make_move():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    game_state = load_board(conversation_id_hash)
    if not game_state:
        return jsonify({"success": False, "message": "No game found"}), 404

    data = request.get_json()

    if "move" not in data:
        return (
            jsonify({"success": False, "message": "Missing move in request data"}),
            400,
        )

    move = data["move"]
    # sometimes if there is an error we will get the same move twice
    if len(game_state.move_history) > 0 and move == game_state.move_history[-1]:
        return jsonify(get_board_state(conversation_id_hash, game_state))
    # check the move is legal
    try:
        if move in get_legal_move_list(game_state.board):
            # make the move
            game_state.board.push_san(move)
            game_state.move_history.append(move)
            save_board(conversation_id_hash, game_state)
            return jsonify(get_board_state(conversation_id_hash, game_state))
        else:
            logging.error("Illegal move: " + move)
            board_state = get_board_state(conversation_id_hash, game_state)
            board_state["error_message"] = "Illegal move - make sure you use SAN"
            return (
                jsonify(board_state),
                400,
            )
    except ValueError as e:
        logging.error("Invalid move format: " + move)
        logging.error(e)
        board_state = get_board_state(conversation_id_hash, game_state)
        board_state["error_message"] = "Invalid move format - use SAN"
        return (
            jsonify(board_state),
            400,
        )


@app.route("/api/fen", methods=["GET"])
def get_fen():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    game_state = load_board(conversation_id_hash)
    if not game_state:
        return jsonify({"success": False, "message": "No game found"}), 404
    return jsonify({"FEN": game_state.board.fen()})


@app.route("/api/move_history", methods=["GET"])
def get_move_history():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    game_state = load_board(conversation_id_hash)
    if not board:
        return jsonify({"success": False, "message": "No game found"}), 404
    moves = format_moves(game_state.move_history)
    return jsonify({"move_history": moves})


@app.route("/board.svg", methods=["GET"])
def board():
    # get the query param cid - this is the conversation ID
    conversation_id_hash = request.args.get("cid")
    move = request.args.get("m")
    move = int(move)
    game_state = load_board(conversation_id_hash, move)

    svg_data = chess.svg.board(board=game_state.board, size=400)
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
