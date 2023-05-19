import pytest
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import MagicMock, patch
from chessgpt.database.dynamodb import Database
from chessgpt.game_state.game_state import GameState
from chessgpt.routes import get_fen_routes
import chess


# create a pytest fixture to initialize a Flask test client
@pytest.fixture
def database():
    db = MagicMock()
    db.load_game_state = MagicMock()
    yield db


@pytest.fixture
def client(database):
    app = Flask(__name__)
    app.logger = MagicMock()
    app.database = database
    get_fen_routes(app)  # register the route
    with app.test_client() as client:
        yield client


def test_get_fen_success(database: Database, client: FlaskClient):
    board = chess.Board()

    # Mock the GameState object returned by load_board
    mock_game_state = GameState(
        board=MagicMock(fen=MagicMock(return_value=board.fen())),  # Mocked chess.Board
        move_history=[],
        assistant_color="white",
        elo=1200,
        created="2023-01-01",
        updated="2023-01-02",
    )
    database.load_game_state.return_value = mock_game_state

    response = client.get("/api/fen", headers={"Openai-Conversation-Id": "testcid"})

    assert response.status_code == 200
    assert response.json["FEN"] == board.fen()


def test_get_fen_no_game_found(database: Database, client: FlaskClient):
    # load_board returns None to simulate no game found
    database.load_game_state.return_value = None

    response = client.get("/api/fen", headers={"Openai-Conversation-Id": "testcid"})

    assert response.status_code == 404
    assert not response.json["success"]
    assert response.json["message"] == "No game found"
