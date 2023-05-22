import chess
from logging import getLogger
from chessgpt.game_state.game_state import get_game_over_reason, GameState

# An arbitrary GameState with only kings remaining, leading to insufficient material
stalemate_state = GameState(
    chess.Board(fen="8/8/8/8/8/8/4K3/4k3 w - - 0 1"), [], "", 0, "", ""
)

# An arbitrary GameState with a position set up for checkmate
checkmate_state = GameState(
    chess.Board(fen="7k/5KQ1/8/8/8/8/8/8 b - - 0 1"), [], "", 0, "", ""
)

# For these tests, a basic logger is sufficient.
logger = getLogger()


def test_stalemate():
    result = get_game_over_reason(logger, stalemate_state, True)
    assert (
        result == "Game ended in insufficient material (K vs. K, K vs. KB, or K vs. KN)"
    )


def test_checkmate_user_wins():
    result = get_game_over_reason(logger, checkmate_state, False)
    assert result == "The user won by Checkmate!"


def test_checkmate_assistant_wins():
    result = get_game_over_reason(logger, checkmate_state, True)
    assert result == "The assistant won by Checkmate!"
