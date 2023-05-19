from unittest.mock import MagicMock
import pytest
from flask import Flask
from flask.testing import FlaskClient
from chessgpt.routes.levels import get_levels_routes


# create a pytest fixture to initialize a Flask test client
@pytest.fixture
def client():
    app = Flask(__name__)
    app.logger = MagicMock()
    app.dynamodb_client = MagicMock()
    app.GAMES_TABLE = "test_games_table"
    get_levels_routes(app)  # register the route
    with app.test_client() as client:
        yield client


def test_levels(client: FlaskClient):
    response = client.get("/api/levels", headers={"Openai-Conversation-Id": "testcid"})

    assert response.status_code == 200
    # check that we got an array of levels
    assert isinstance(response.json, list)
    # check that each level has a name, description and elo
    for level in response.json:
        assert "name" in level
        assert "description" in level
        assert "elo" in level
