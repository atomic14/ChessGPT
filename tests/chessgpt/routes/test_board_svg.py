import pytest
from unittest.mock import MagicMock, patch
from unittest.mock import ANY
from flask import Flask

# import your register_routes function
from chessgpt.routes.board_svg import board_routes


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
    board_routes(app)
    with app.test_client() as client:
        yield client


def test_missing_b(client):
    response = client.get("/board.svg?")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "message": "Missing b query parameter",
    }


def test_invalid_b(client):
    response = client.get("/board.svg?b=abc")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "message": "Invalid b query parameter",
    }


@patch("chessgpt.routes.board_svg.decode_board", return_value=MagicMock())
def test_b_query_param(mock_decode_board, client):
    response = client.get("/board.svg?b=testb")

    # assert decode_board is called with the correct arguments
    mock_decode_board.assert_called_once_with("testb")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
