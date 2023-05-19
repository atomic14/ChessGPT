from datetime import datetime
import os
import boto3
import chess

from chessgpt.game_state.game_state import GameState


def get_dynamodb_client():
    # setup the dynamodb client
    if os.environ.get("IS_OFFLINE") == "True":
        print("Running in offline mode")
        session = boto3.Session(
            aws_access_key_id="DUMMY", aws_secret_access_key="DUMMY"
        )
        return session.resource(
            "dynamodb", region_name="localhost", endpoint_url="http://localhost:8000"
        ).meta.client
    else:
        session = boto3.Session()
        return session.resource("dynamodb").meta.client


class Database:
    def __init__(self, logger):
        self.logger = logger
        self.table_name = os.environ["GAMES_TABLE"]
        self.dynamodb_client = get_dynamodb_client()

    def load_game_state(self, conversation_id_hash) -> GameState:
        self.logger.debug("Loading board state from dynamoDB")
        result = self.dynamodb_client.get_item(
            TableName=self.table_name, Key={"conversationId": conversation_id_hash}
        )
        item = result.get("Item")
        if not item:
            return None  # type: ignore

        moves_string = item.get("moves")
        if not moves_string:
            moves = []
        else:
            moves = moves_string.split(",")
        board = chess.Board()
        for move in moves:
            board.push_san(move)
        assistant_color = item.get("assistant_color")
        elo = int(item.get("elo", "2000"))
        elo = max(1350, min(2850, elo))
        now = datetime.utcnow().timestamp()
        created = int(item.get("created", now))
        updated = int(item.get("updated", now))
        return GameState(board, moves, assistant_color, elo, created, updated)

    def save_game_state(self, conversation_id_hash, game_state: GameState):
        # save the board state to dynamoDB - we'll just save the move history
        self.logger.debug("Saving board state to dynamoDB")
        self.dynamodb_client.put_item(
            TableName=self.table_name,
            Item={
                "conversationId": conversation_id_hash,
                "moves": ",".join(game_state.move_history),
                "assistant_color": game_state.assistant_color,
                "elo": str(game_state.elo),
                "created": str(game_state.created),
                "updated": str(game_state.updated),
            },
        )
