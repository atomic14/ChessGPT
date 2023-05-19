from collections import namedtuple

import chess
from chessgpt.compression.huffman import decode_board, encode_board
from chessgpt.stockfish.stockfish import get_best_move, get_best_moves, get_stockfish

# create a named tuple to hold the game state
GameState = namedtuple(
    "GameState",
    ["board", "move_history", "assistant_color", "elo", "created", "updated"],
)


# get the list of legal moves in SAN format
def get_legal_move_list(logger, board):
    legal_moves = [board.san(move) for move in board.legal_moves]
    logger.debug("Legal moves: " + str(legal_moves))
    return legal_moves


def get_markdown(logger, conversation_id_hash, game_state: GameState, scheme, host):
    # encode the board as a base64 string
    encoded_board = encode_board(game_state.board)
    try:
        # check the results can be decoded
        decode_board(encoded_board)
    except Exception as e:
        logger.error("Error decoding board: " + str(e))
        logger.error("Encoded board: " + encoded_board)
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
    logger.info("Markdown: " + markdown)
    return markdown


def format_moves(logger, move_history):
    # pair the moves from white and black
    moves = []
    for i in range(0, len(move_history), 2):
        if i + 1 < len(move_history):
            moves.append(f"{int(i/2 + 1)}. {move_history[i]} {move_history[i + 1]}")
        else:
            moves.append(f"{int(i/2 + 1)}. {move_history[i]}")
    logger.debug("Moves: " + str(moves))
    return moves


def get_game_over_reason(logger, game_state: GameState, isUsersTurn: bool):
    board = game_state.board
    if board.is_game_over():
        logger.debug("Game over!")
        outcome = board.outcome()

        termination_reasons = {
            chess.Termination.CHECKMATE: "The assistant won by Checkmate!"
            if isUsersTurn
            else "The user lost to Checkmate!",
            chess.Termination.STALEMATE: "Game ended in a stalemate!",
            chess.Termination.THREEFOLD_REPETITION: "Game ended in a threefold repetition!",
            chess.Termination.FIVEFOLD_REPETITION: "Game ended in a fivefold repetition!",
            chess.Termination.INSUFFICIENT_MATERIAL: "Game ended in insufficient material (K vs. K, K vs. KB, or K vs. KN)",  # noqa: E501
        }

        if outcome is not None:
            return termination_reasons.get(
                outcome.termination, "Game ended in an unspecified way!"
            )


def get_board_state_for_assistant(
    logger, conversation_id_hash, game_state: GameState, turn, scheme, host
):
    stockfish = get_stockfish(game_state.elo, game_state.board.fen())
    best_moves = get_best_move(stockfish)
    if best_moves:
        best_moves_san = [game_state.board.san(chess.Move.from_uci(best_moves))]
    else:
        best_moves_san = []
    logger.debug("Best moves for assistant: " + str(best_moves_san))
    instructions = (
        f"It's the assistant's turn. The assistant is playing {turn}. Pick a move from the following best moves for {turn}: {', '.join(best_moves_san)}. "  # noqa: E501
        + "Use the make move API to make the move for the assistant and the show the board to the user using the markdown from the display field."  # noqa: E501
    )
    return {
        "game_over": False,
        "display": get_markdown(logger, conversation_id_hash, game_state, scheme, host),
        "best_moves": ", ".join(best_moves_san),
        "EXTRA_INFORMATION_TO_ASSISTANT": instructions,
    }


def get_board_state_for_user(
    logger, conversation_id_hash, game_state: GameState, turn, scheme, host
):
    stockfish = get_stockfish(2850, game_state.board.fen())
    best_moves = get_best_moves(stockfish)
    best_moves_san = [
        game_state.board.san(chess.Move.from_uci(move["Move"])) for move in best_moves
    ]
    instructions = (
        f"It's the user's turn to move. The user is playing {turn}. Show the board to the user using the markdown from the display field. Prompt the user to make their move using SAN notation"  # noqa: E501
        + " (e.g. e4, Nf3, etc). Use the make move API to make the move for the user."
    )
    return {
        "game_over": False,
        "display": get_markdown(logger, conversation_id_hash, game_state, scheme, host),
        "best_moves": ", ".join(best_moves_san),
        "EXTRA_INFORMATION_TO_ASSISTANT": instructions,
    }


def get_board_state_for_game_over(
    logger, conversation_id_hash, game_state: GameState, turn, scheme, host
):
    game_over_reason = get_game_over_reason(
        logger, game_state, turn != game_state.assistant_color
    )
    instructions = f"Game over! {game_over_reason}"
    return {
        "game_over": True,
        "display": get_markdown(logger, conversation_id_hash, game_state, scheme, host),
        "best_moves": "",
        "EXTRA_INFORMATION_TO_ASSISTANT": instructions,
    }


def get_board_state(logger, conversation_id_hash, game_state: GameState, scheme, host):
    # work out who's turn is it from the move_history
    if len(game_state.move_history) % 2 == 0:
        turn = "white"
    else:
        turn = "black"
    # check for game over
    if game_state.board.is_game_over():
        return get_board_state_for_game_over(
            logger, conversation_id_hash, game_state, turn, scheme, host
        )
    if turn == game_state.assistant_color:
        return get_board_state_for_assistant(
            logger, conversation_id_hash, game_state, turn, scheme, host
        )
    else:
        return get_board_state_for_user(
            logger, conversation_id_hash, game_state, turn, scheme, host
        )
