import pytest
from unittest.mock import MagicMock, patch
from unittest.mock import ANY
from flask import Flask

# import your register_routes function
from chessgpt.routes.board_svg import board
from chessgpt.utils.openai import get_conversation_id_hash


@pytest.fixture
def client():
    app = Flask(__name__)
    app.logger = MagicMock()
    app.dynamodb_client = MagicMock()
    app.GAMES_TABLE = "test_games_table"
    board(app)
    with app.test_client() as client:
        yield client


@patch("chessgpt.routes.board_svg.load_board", return_value=MagicMock())
def test_valid_cid_and_m(mock_load_board, client):
    # mock the return value of load_board
    mock_load_board.return_value.board = MagicMock()

    response = client.get("/board.svg?cid=testcid&m=1")

    # assert load_board is called with the correct arguments
    mock_load_board.assert_called_once_with(ANY, ANY, ANY, "testcid", 1)

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"


@patch("chessgpt.routes.board_svg.load_board", return_value=None)
def test_invalid_cid_and_m(mock_load_board, client):
    response = client.get("/board.svg?cid=testcid&m=1")

    # assert load_board is called with the correct arguments
    mock_load_board.assert_called_once_with(ANY, ANY, ANY, "testcid", 1)

    assert response.status_code == 404
    assert response.get_json() == {"success": False, "message": "No game found"}


def test_missing_cid(client):
    response = client.get("/board.svg?m=1")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "message": "Missing cid query parameter",
    }


def test_missing_m(client):
    response = client.get("/board.svg?cid=testcid")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "message": "Missing m query parameter",
    }


def test_invalid_m(client):
    response = client.get("/board.svg?cid=testcid&m=abc")

    assert response.status_code == 400
    assert response.get_json() == {
        "success": False,
        "message": "Invalid m query parameter",
    }


@patch("chessgpt.routes.board_svg.decode_board", return_value=MagicMock())
def test_b_query_param(mock_decode_board, client):
    response = client.get("/board.svg?b=testb")

    # assert decode_board is called with the correct arguments
    mock_decode_board.assert_called_once_with("testb")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
