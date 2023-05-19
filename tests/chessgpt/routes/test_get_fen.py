import pytest
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import MagicMock, patch
from chessgpt.game_state.game_state import GameState
from chessgpt.routes import fen
import chess


# create a pytest fixture to initialize a Flask test client
@pytest.fixture
def client():
    app = Flask(__name__)
    app.logger = MagicMock()
    app.dynamodb_client = MagicMock()
    app.GAMES_TABLE = "test_games_table"
    fen.get_fen(app)  # register the route
    with app.test_client() as client:
        yield client


@patch("chessgpt.routes.fen.load_board")
def test_get_fen_success(mock_load_board, client: FlaskClient):
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
    mock_load_board.return_value = mock_game_state

    response = client.get("/api/fen", headers={"Openai-Conversation-Id": "testcid"})

    assert response.status_code == 200
    assert response.json["FEN"] == board.fen()


@patch("chessgpt.routes.fen.load_board")
def test_get_fen_no_game_found(mock_load_board, client: FlaskClient):
    # load_board returns None to simulate no game found
    mock_load_board.return_value = None

    response = client.get("/api/fen", headers={"Openai-Conversation-Id": "testcid"})

    assert response.status_code == 404
    assert not response.json["success"]
    assert response.json["message"] == "No game found"
