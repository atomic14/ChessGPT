from unittest.mock import Mock
from chessgpt.routes.move import try_make_move
import chess


def test_try_make_move():
    # Mocking app and game_state objects
    app = Mock()
    app.logger = Mock()

    game_state = Mock()
    game_state.board = chess.Board()
    game_state.move_history = []

    # Testing a legal move
    assert try_make_move(app, game_state, "e4")
    assert game_state.move_history == ["e4"]

    # Testing an illegal move
    assert not try_make_move(app, game_state, "c4")
    assert game_state.move_history == ["e4"]

    # Testing a move not in SAN format but legal
    assert try_make_move(app, game_state, "e7e5")
    assert game_state.move_history == ["e4", "e5"]
