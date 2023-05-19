import pytest
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import MagicMock, Mock, patch
from chessgpt.database.dynamodb import Database
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
def database():
    db = MagicMock()
    db.load_game_state = MagicMock()
    db.save_game_state = MagicMock()
    yield db


@pytest.fixture
def client(database):
    app = Flask(__name__)
    app.logger = MagicMock()
    app.database = database
    make_move_routes(app)  # register the route
    with app.test_client() as client:
        yield client


def test_make_san_move_success(database: Database, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    database.load_game_state.return_value = mock_game_state

    response = client.post(
        "/api/move", headers={"Openai-Conversation-Id": "testcid"}, json={"move": "e4"}
    )

    assert response.status_code == 200


def test_make_uci_move_success(database: Database, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    database.load_game_state.return_value = mock_game_state

    response = client.post(
        "/api/move",
        headers={"Openai-Conversation-Id": "testcid"},
        json={"move": "e2e4"},
    )

    assert response.status_code == 200


def test_make_invalid_move_fails(database: Database, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    database.load_game_state.return_value = mock_game_state

    response = client.post(
        "/api/move",
        headers={"Openai-Conversation-Id": "testcid"},
        json={"move": "e6"},
    )

    assert response.status_code == 400


def test_make_garbage_move_fails(database: Database, client: FlaskClient):
    # Mock the GameState object returned by load_board
    mock_game_state = Mock()
    mock_game_state.board = chess.Board()
    mock_game_state.move_history = []
    database.load_game_state.return_value = mock_game_state

    response = client.post(
        "/api/move",
        headers={"Openai-Conversation-Id": "testcid"},
        json={"move": "wibble"},
    )

    assert response.status_code == 400
