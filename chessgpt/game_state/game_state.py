from collections import namedtuple
import datetime

import chess
from app import app
from chessgpt.compression.huffman import decode_board, encode_board
from chessgpt.stockfish.stockfish import get_best_move, get_best_moves, get_stockfish

# create a named tuple to hold the game state
GameState = namedtuple(
    "GameState",
    ["board", "move_history", "assistant_color", "elo", "created", "updated"],
)


# save the board state to dynamoDB - we'll just save the move history
def save_board(conversation_id_hash: str, game_state: GameState):
    app.dynamodb_client.put_item(
        TableName=app.GAMES_TABLE,
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
    result = app.dynamodb_client.get_item(
        TableName=app.GAMES_TABLE, Key={"conversationId": conversation_id_hash}
    )
    item = result.get("Item")
    if not item:
        return None  # type: ignore

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


def get_markdown(conversation_id_hash, game_state: GameState, scheme, host):
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
        markdown = (
            f"![Board]({scheme}://{host}/board.svg?cid={conversation_id_hash}&m={m})"
        )
        return markdown
    # encoding worked ok, so use the new method
    markdown = f"![Board]({scheme}://{host}/board.svg?b={encoded_board})"
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
                    return "The assistant won by Checkmate!"
                else:
                    return "The user lost to Checkmate!"
            elif outcome.termination == chess.Termination.STALEMATE:
                return "Game ended in a stalemate!"
            elif outcome.termination == chess.Termination.THREEFOLD_REPETITION:
                return "Game ended in a threefold repetition!"
            elif outcome.termination == chess.Termination.FIVEFOLD_REPETITION:
                return "Game ended in a fivefold repetition!"
            elif outcome.termination == chess.Termination.INSUFFICIENT_MATERIAL:
                return "Game ended in insufficient material (K vs. K, K vs. KB, or K vs. KN)"
            else:
                return "Game ended in an unspecified way!"


def get_board_state(conversation_id_hash, game_state: GameState, scheme, host):
    # work out who's turn is it from the move_history
    if len(game_state.move_history) % 2 == 0:
        turn = "white"
    else:
        turn = "black"
    # check for game over
    if game_state.board.is_game_over():
        game_over_reason = get_game_over_reason(
            game_state, turn != game_state.assistant_color
        )
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
                f"It's the assistant's turn. The assistant is playing {turn}. Pick a move from the following best moves for {turn}: {', '.join(best_moves_san)}. "  # noqa: E501
                + "Use the make move API to make the move for the assistant and the show the board to the user using the markdown from the display field."  # noqa: E501
            )
        else:
            instructions = (
                f"It's the user's turn to move. The user is playing {turn}. Show the board to the user using the markdown from the display field. Prompt the user to make their move using SAN notation"  # noqa: E501
                + " (e.g. e4, Nf3, etc). Use the make move API to make the move for the user."
            )

    return {
        "game_over": game_state.board.is_game_over(),
        "display": get_markdown(conversation_id_hash, game_state, scheme, host),
        "best_moves": ", ".join(best_moves_san),
        "EXTRA_INFORMATION_TO_ASSISTANT": instructions,
    }
