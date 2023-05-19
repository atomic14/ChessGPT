import pytest
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import MagicMock, Mock, patch
from chessgpt.game_state import GameState
from chessgpt.routes.move import try_make_move, make_move_routes
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


# create a pytest fixture to initialize a Flask test client
@pytest.fixture
def client():
    app = Flask(__name__)
    app.logger = MagicMock()
    app.dynamodb_client = MagicMock()
    app.GAMES_TABLE = "test_games_table"
    make_move_routes(app)  # register the route
    with app.test_client() as client:
        yield client


@patch("chessgpt.routes.move.load_board")
@patch("chessgpt.routes.move.save_board")
def test_make_san_move_success(mock_save_board, mock_load_board, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    mock_load_board.return_value = mock_game_state

    response = client.post(
        "/api/move", headers={"Openai-Conversation-Id": "testcid"}, json={"move": "e4"}
    )

    assert response.status_code == 200


@patch("chessgpt.routes.move.load_board")
@patch("chessgpt.routes.move.save_board")
def test_make_uci_move_success(mock_save_board, mock_load_board, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    mock_load_board.return_value = mock_game_state

    response = client.post(
        "/api/move",
        headers={"Openai-Conversation-Id": "testcid"},
        json={"move": "e2e4"},
    )

    assert response.status_code == 200


@patch("chessgpt.routes.move.load_board")
def test_make_invalid_move_fails(mock_load_board, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    mock_load_board.return_value = mock_game_state

    response = client.post(
        "/api/move",
        headers={"Openai-Conversation-Id": "testcid"},
        json={"move": "e6"},
    )

    assert response.status_code == 400


@patch("chessgpt.routes.move.load_board")
def test_make_garbage_move_fails(mock_load_board, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    mock_load_board.return_value = mock_game_state

    response = client.post(
        "/api/move",
        headers={"Openai-Conversation-Id": "testcid"},
        json={"move": "wibble"},
    )

    assert response.status_code == 400
