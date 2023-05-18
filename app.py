import collections
import os
import shutil
import boto3
from flask import Flask, jsonify, make_response, request, send_from_directory, Response
import chess
import chess.svg
import chess.pgn
import logging
from logging.handlers import SysLogHandler
import hashlib
import datetime
from flask_cors import CORS
from stockfish import Stockfish
import base64

app = Flask(__name__)
CORS(app)

app.logger.setLevel(logging.INFO)

papertrail_app_name = os.environ.get("PAPERTRAIL_APP_NAME")
# set the name of the app for papertrail
if papertrail_app_name:
    class RequestFormatter(logging.Formatter):
        def format(self, record):
            if hasattr(record, 'pathname'):
                # ensure we have a request context
                if request:
                    record.pathname = request.path
            return super().format(record)

    app.logger.name = papertrail_app_name
    syslog = SysLogHandler(address=("logs6.papertrailapp.com", 47875))
    syslog.setLevel(logging.INFO)
    formatter = RequestFormatter(f"{papertrail_app_name}: chess %(levelname)s %(pathname)s %(message)s")
    syslog.setFormatter(formatter)
    app.logger.addHandler(syslog)

app.logger.info("Starting app")


def exclude_from_log(route_func):
    route_func._exclude_from_log = True
    return route_func


@app.before_request
def log_request_info():
    if not getattr(request.endpoint, "_exclude_from_log", False):
        # dump the query params and body
        app.logger.info("Request: %s", request.url)
        # app.logger.info("Body: %s", request.get_data())


@app.after_request
def log_response_info(response):
    # # Only log if the response is JSON
    # if (
    #     not getattr(request.endpoint, "_exclude_from_log", False)
    #     and response.mimetype == "application/json"
    # ):
    #     app.logger.info("Response: %s", response.get_data(as_text=True))
    return response


# create a named tuple to hold the game state
GameState = collections.namedtuple(
    "GameState",
    ["board", "move_history", "assistant_color", "elo", "created", "updated"],
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
        "elo": 1350,
        "description": "The assistant will play at an Elo rating of 1350. This is a good level for beginners.",
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
        "elo": 2850,
        "description": "The assistant will play at an Elo rating of 2850. This is a good level for grandmasters.",
    },
]

HUFFMAN_DICT = {
    ".": "1",
    "P": "010",
    "p": "001",
    "B": "00010",
    "N": "00000",
    "R": "01110",
    "b": "00011",
    "n": "00001",
    "r": "01101",
    "K": "011110",
    "Q": "011001",
    "k": "011111",
    "q": "011000",
}

REVERSE_HUFFMAN_DICT = {v: k for k, v in HUFFMAN_DICT.items()}


def string_to_bytes(s):
    return int(s, 2).to_bytes((len(s) + 7) // 8, byteorder="big")


def bytes_to_string(b):
    return bin(int.from_bytes(b, byteorder="big"))[2:].zfill(len(b) * 8)


def encode_board(board):
    board_string = str(board).replace(" ", "").replace("\n", "")
    binary_string = "".join(HUFFMAN_DICT[char] for char in board_string)
    # Add padding to the end of the binary string
    padded_binary_string = binary_string.ljust((len(binary_string) + 7) // 8 * 8, "0")
    b = string_to_bytes(padded_binary_string)
    return base64.urlsafe_b64encode(b).decode()


def decode_board(encoded_board):
    code = ""
    position = 0
    board = chess.Board()
    board.clear()
    for bit in bytes_to_string(base64.urlsafe_b64decode(encoded_board.encode())):
        code += bit
        if code in REVERSE_HUFFMAN_DICT:
            piece = REVERSE_HUFFMAN_DICT[code]
            if piece != ".":
                x = position % 8
                y = 7 - position // 8
                board.set_piece_at(y * 8 + x, chess.Piece.from_symbol(piece))
            position += 1
            code = ""
            if position == 64:
                break
    return board


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


def get_best_move(stockfish):
    return stockfish.get_best_move()


# save the board state to dynamoDB - we'll just save the move history
def save_board(conversation_id_hash: str, game_state: GameState):
    dynamodb_client.put_item(
        TableName=GAMES_TABLE,
        Item={
            "conversationId": conversation_id_hash,
            "moves": ",".join(game_state.move_history),
            "assistant_color": game_state.assistant_color,
            "elo": str(game_state.elo),
            "created": str(game_state.created),
            "updated": str(game_state.updated),
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
        return None

    moves_string = item.get("moves")
    if not moves_string:
        moves = []
    else:
        moves = moves_string.split(",")
    app.logger.debug("Moves: " + str(moves))
    board = chess.Board()
    if max_move is None:
        max_move = len(moves)
    for move in moves[:max_move]:
        board.push_san(move)
    assistant_color = item.get("assistant_color")
    elo = int(item.get("elo", "2000"))
    elo = max(1350, min(2850, elo))
    now = datetime.datetime.utcnow().timestamp()
    created = int(item.get("created", now))
    updated = int(item.get("updated", now))
    return GameState(board, moves, assistant_color, elo, created, updated)


# get the list of legal moves in SAN format
def get_legal_move_list(board):
    legal_moves = [board.san(move) for move in board.legal_moves]
    return legal_moves


def get_markdown(conversation_id_hash, game_state: GameState):
    # encode the board as a base64 string
    encoded_board = encode_board(game_state.board)
    try:
        # check the results can be decoded
        decode_board(encoded_board)
    except Exception as e:
        app.logger.error("Error decoding board: " + str(e))
        app.logger.error("Encoded board: " + encoded_board)
        # fallback to the old method
        if game_state.move_history:
            m = len(game_state.move_history)
        else:
            m = 0
        markdown = f"![Board]({request.scheme}://{request.host}/board.svg?cid={conversation_id_hash}&m={m})"
        return markdown
    # encoding worked ok, so use the new method
    markdown = (
        f"![Board]({request.scheme}://{request.host}/board.svg?b={encoded_board})"
    )
    app.logger.info("Markdown: " + markdown)
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


def get_game_over_reason(game_state: GameState, isUsersTurn: bool):
    board = game_state.board
    if board.is_game_over():
        outcome = board.outcome()
        if outcome is not None:
            if outcome.termination == chess.Termination.CHECKMATE:
                if isUsersTurn:
                    return 'The assistant won by Checkmate!'
                else:
                    return 'The user lost to Checkmate!'                    
            elif outcome.termination == chess.Termination.STALEMATE:
                return 'Game ended in a stalemate!'
            elif outcome.termination == chess.Termination.THREEFOLD_REPETITION:
                return 'Game ended in a threefold repetition!'
            elif outcome.termination == chess.Termination.FIVEFOLD_REPETITION:
                return 'Game ended in a fivefold repetition!'
            elif outcome.termination == chess.Termination.INSUFFICIENT_MATERIAL:
                return 'Game ended in insufficient material (K vs. K, K vs. KB, or K vs. KN)'
            else:
                return 'Game ended in an unspecified way!'
          

def get_board_state(conversation_id_hash, game_state: GameState):
    # work out who's turn is it from the move_history
    if len(game_state.move_history) % 2 == 0:
        turn = "white"
    else:
        turn = "black"
    # check for game over
    if game_state.board.is_game_over():
        game_over_reason = get_game_over_reason(game_state, turn != game_state.assistant_color)
        instructions = f"Game over! {game_over_reason}"
        # no legal moves
        best_moves_san = []
    else:
        # get the best moves for the assistant or user (give the user grandmaster moves!)
        best_move_elo = game_state.elo if turn == game_state.assistant_color else 2850
        stockfish = get_stockfish(best_move_elo, game_state.board.fen())
        if turn == game_state.assistant_color:
            best_moves = get_best_move(stockfish)
            if best_moves:
                best_moves_san = [game_state.board.san(chess.Move.from_uci(best_moves))]
            else:
                best_moves_san = []
        else:
            best_moves = get_best_moves(stockfish)
            best_moves_san = [
                game_state.board.san(chess.Move.from_uci(move["Move"]))
                for move in best_moves
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
                + " (e.g. e4, Nf3, etc). Use the make move API to make the move for the user."
            )

    return {
        "game_over": game_state.board.is_game_over(),
        "display": get_markdown(conversation_id_hash, game_state),
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
    if elo < 1350 or elo > 2850:
        app.logger.error("elo out of range in request data: " + str(data["elo"]))
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
    # check the assistant_color is valid
    assistant_color = data["assistant_color"]
    if assistant_color not in ["white", "black"]:
        app.logger.error("Invalid assistant_color in request data: " + assistant_color)
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
    save_board(conversation_id_hash, game_state)
    app.logger.info(f"New game started. Level {elo} assistant color {assistant_color}")
    return jsonify(get_board_state(conversation_id_hash, game_state))


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
            return jsonify(get_board_state(conversation_id_hash, game_state))
        else:
            app.logger.error("Illegal move: " + move)
            board_state = get_board_state(conversation_id_hash, game_state)
            board_state["error_message"] = "Illegal move - make sure you use SAN"
            return (
                jsonify(board_state),
                400,
            )
    except ValueError as e:
        app.logger.error("Invalid move format: " + move)
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
        app.logger.error("No game found for conversation ID: " + conversation_id)
        return jsonify({"success": False, "message": "No game found"}), 404
    return jsonify({"FEN": game_state.board.fen()})


@app.route("/api/move_history", methods=["GET"])
def get_move_history():
    conversation_id = request.headers.get("Openai-Conversation-Id")
    conversation_id_hash = get_conversation_id_hash(conversation_id)
    game_state = load_board(conversation_id_hash)
    if not board:
        app.logger.error("No game found for conversation ID: " + conversation_id)
        return jsonify({"success": False, "message": "No game found"}), 404
    moves = format_moves(game_state.move_history)
    return jsonify({"move_history": moves})


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
                jsonify({"success": False, "message": "Missing cid query parameter"}),
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

        game_state = load_board(conversation_id_hash, int(move))
        if not game_state:
            app.logger.error("No game found for cid " + conversation_id_hash)
            return jsonify({"success": False, "message": "No game found"}), 404
        board = game_state.board

    svg_data = chess.svg.board(board=board, size=400)
    response = Response(svg_data, mimetype="image/svg+xml")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/.well-known/ai-plugin.json")
@exclude_from_log
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
@exclude_from_log
def serve_openai_yaml():
    # read in the file
    with open("openapi.yaml", "r") as f:
        data = f.read()
        # replace the string PLUGIN_HOSTNAME with the actual hostname
        data = data.replace("PLUGIN_HOSTNAME", request.host)
        data = data.replace("PROTOCOL", request.scheme)
        # return the modified file
        response = Response(data, mimetype="text/yaml")
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response


@app.route("/")
@app.route("/index.html")
@exclude_from_log
def index():
    return send_from_directory("static", "index.html")


@app.route("/site.webmanifest")
@exclude_from_log
def site_manifest():
    return send_from_directory("static", "site.webmanifest")


@app.route("/images/<path:path>")
@exclude_from_log
def send_image(path):
    response = send_from_directory("static/images", path)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/logo.png")
@exclude_from_log
def serve_logo():
    # cache for 24 hours
    response = send_from_directory("static", "logo.png")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/robots.txt")
@exclude_from_log
def serve_robots():
    # cache for 24 hours
    response = send_from_directory("static", "robots.txt")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/favicon.ico")
@exclude_from_log
def serve_favicon():
    # cache for 24 hours
    response = send_from_directory("static/images/", "favicon.ico")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.errorhandler(404)
def resource_not_found(e):
    return make_response(jsonify(error="Not found!"), 404)


@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(e)
    return make_response(jsonify(error="Internal Server Error!"), 500)
