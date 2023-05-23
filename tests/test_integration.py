import pytest
import os
import subprocess
import requests
import time
import socket
import time
import re


class EnvironmentSetup:
    def __init__(self):
        self.server_process = None
        self.docker_process = None

    def start_server(self):
        # Run your server start command
        self.server_process = subprocess.Popen(
            ["sls", "wsgi", "serve", "-p", "5204"],
            env=dict(os.environ, IS_OFFLINE="True"),
        )

    def start_docker(self):
        # Start Docker Compose
        self.docker_process = subprocess.Popen(["docker-compose", "up"])

    def seed_database(self):
        # This is a blocking call that will wait for the seed script to finish
        subprocess.check_call(["sls", "dynamodb", "migrate"])

    def stop_server(self):
        if self.server_process is not None:
            self.server_process.terminate()

    def stop_docker(self):
        if self.docker_process is not None:
            subprocess.call(["docker-compose", "down"])


def wait_for_port(port, host="localhost", timeout=60.0):
    """Wait until a port starts accepting TCP connections.
    Args:
        port (int): Port number
        host (str): Host address on which the port should exist
        timeout (float): In seconds. How long to wait before raising errors.
    Raises:
        TimeoutError: The port isn't accepting connection after time specified in `timeout`.
    """
    start_time = time.perf_counter()
    while True:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.01)
            if time.perf_counter() - start_time >= timeout:
                raise TimeoutError(
                    f"Timed out while waiting for port {port} on {host} to start accepting connections."
                )


@pytest.fixture(scope="module", autouse=True)
def test_env():
    env = EnvironmentSetup()

    # Start dynamodb and seed the database
    env.start_docker()
    wait_for_port(8000)
    env.seed_database()
    # Start server
    env.start_server()
    wait_for_port(5204)

    yield  # This is where the testing happens

    # Stop server and docker compose after tests
    env.stop_server()
    env.stop_docker()


BASE_URL = "http://localhost:5204"


def check_image(display_markdown):
    # check the image in the display markdown - use a regex to extract it
    inage_regex = re.compile(r"!\[Board\]\((.*)\)")
    image_url = inage_regex.search(display_markdown).group(1)
    # get the image
    response = requests.get(image_url)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/svg+xml; charset=utf-8"


@pytest.mark.integration
def test_chess_api():
    headers = {
        "Openai-Conversation-Id": "testcid",
    }
    # Test /api/levels
    response = requests.get(f"{BASE_URL}/api/levels", headers=headers)
    assert response.status_code == 200
    levels = response.json()
    assert isinstance(levels, list)

    # Test /api/new_game
    new_game_payload = {
        "assistant_color": "white",
        "elo": 1500,
    }
    response = requests.post(
        f"{BASE_URL}/api/new_game", json=new_game_payload, headers=headers
    )
    assert response.status_code == 200
    new_game_state = response.json()
    assert "game_over" in new_game_state
    assert "display" in new_game_state

    # Test /api/move
    move_payload = {
        "move": "e4",
    }
    response = requests.post(f"{BASE_URL}/api/move", json=move_payload, headers=headers)
    assert response.status_code == 200
    move_state = response.json()
    assert "game_over" in move_state
    assert "display" in move_state

    assert move_state["game_over"] is False

    # make another move
    move_payload = {
        "move": "e5",
    }
    response = requests.post(f"{BASE_URL}/api/move", json=move_payload, headers=headers)
    assert response.status_code == 200
    move_state = response.json()
    assert "game_over" in move_state
    assert "display" in move_state

    assert move_state["game_over"] is False
    check_image(move_state["display"])

    # get the move history
    response = requests.get(f"{BASE_URL}/api/move_history", headers=headers)
    assert response.status_code == 200
    move_history_result = response.json()
    move_history = move_history_result["move_history"]
    assert isinstance(move_history, list)
    assert len(move_history) == 1
    assert move_history[0] == "1. e4 e5"

    # get the fen of the board
    response = requests.get(f"{BASE_URL}/api/fen", headers=headers)
    assert response.status_code == 200
    fen_result = response.json()
    fen = fen_result["FEN"]
    assert isinstance(fen, str)
    assert fen == "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
