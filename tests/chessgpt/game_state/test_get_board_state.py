import chess
from logging import getLogger
from unittest.mock import patch, Mock
from chessgpt.game_state.game_state import (
    get_board_state_for_assistant,
    get_board_state_for_user,
    get_board_state,
    GameState,
)

# For these tests, a basic logger is sufficient.
logger = getLogger()


@patch("chessgpt.game_state.game_state.get_stockfish")
@patch("chessgpt.game_state.game_state.get_best_move")
@patch("chessgpt.game_state.game_state.get_markdown")
def test_get_board_state_for_assistant(
    mock_get_markdown, mock_get_best_move, mock_get_stockfish
):
    mock_get_stockfish.return_value = "stockfish"
    mock_get_best_move.return_value = "e2e4"
    mock_get_markdown.return_value = "markdown"

    game_state = GameState(chess.Board(), [], "", 1200, "", "")

    result = get_board_state_for_assistant(
        logger, "hash", game_state, "white", "http", "localhost"
    )

    assert result == {
        "game_over": False,
        "display": "markdown",
        "best_moves": "e4",
        "EXTRA_INFORMATION_TO_ASSISTANT": "It's the assistant's turn. The assistant is playing white. Pick a move from the following best moves for white: e4. Use the make move API to make the move for the assistant and the show the board to the user using the markdown from the display field.",
    }


@patch("chessgpt.game_state.game_state.get_stockfish")
@patch("chessgpt.game_state.game_state.get_best_moves")
@patch("chessgpt.game_state.game_state.get_markdown")
def test_get_board_state_for_user(
    mock_get_markdown, mock_get_best_moves, mock_get_stockfish
):
    # Define a dummy move to return from the mocked get_best_moves function
    dummy_move = [{"Move": "e2e4", "Score": 0.2}, {"Move": "e7e5", "Score": 0.1}]

    mock_get_stockfish.return_value = "stockfish"
    mock_get_best_moves.return_value = dummy_move
    mock_get_markdown.return_value = "markdown"

    game_state = GameState(chess.Board(), [], "", 1200, "", "")

    result = get_board_state_for_user(
        logger, "hash", game_state, "white", "http", "localhost"
    )

    assert result == {
        "game_over": False,
        "display": "markdown",
        "best_moves": "e4, exe5",
        "EXTRA_INFORMATION_TO_ASSISTANT": "It's the user's turn to move. The user is playing white. Show the board to the user using the markdown from the display field. Prompt the user to make their move using SAN notation (e.g. e4, Nf3, etc). Use the make move API to make the move for the user.",
    }


def test_get_board_state():
    # Create the mocks and dummy values
    logger = Mock()
    conversation_id_hash = "dummy_hash"
    scheme = "http"
    host = "localhost"
    board = chess.Board()
    game_state = GameState(board, [], "white", 1600, None, None)

    with patch(
        "chessgpt.game_state.game_state.get_board_state_for_game_over"
    ) as mock_game_over, patch(
        "chessgpt.game_state.game_state.get_board_state_for_assistant"
    ) as mock_assistant, patch(
        "chessgpt.game_state.game_state.get_board_state_for_user"
    ) as mock_user:  # replace 'your_module' with the actual module name
        # Define the return values for the mocks
        mock_game_over.return_value = "game_over_return"
        mock_assistant.return_value = "assistant_return"
        mock_user.return_value = "user_return"

        # Test when game is over
        board.set_fen("7k/5KQ1/8/8/8/8/8/8 b - - 0 1")  # a position where game is over
        result = get_board_state(logger, conversation_id_hash, game_state, scheme, host)
        assert result == "game_over_return"

        # Test when it's assistant's turn
        board.set_fen(
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        )  # a position where it's black's turn
        result = get_board_state(logger, conversation_id_hash, game_state, scheme, host)
        assert result == "assistant_return"

        # Test when it's user's turn
        board.set_fen(
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
        )  # a position where it's white's turn
        game_state = GameState(board, [], "black", 1600, None, None)
        result = get_board_state(logger, conversation_id_hash, game_state, scheme, host)
        assert result == "user_return"
