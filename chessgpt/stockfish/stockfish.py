import os
import shutil
from stockfish import Stockfish

def get_stockfish_path():
    result = shutil.which("stockfish")
    if result is None:
        # locate the binary from ./stockfish
        result = os.path.join(os.path.dirname(__file__), "stockfish/stockfish")
    return result


def get_stockfish(elo, fen):
    stockfish = Stockfish(get_stockfish_path())
    stockfish.set_elo_rating(elo)
    stockfish.set_fen_position(fen)
    return stockfish


def get_best_moves(stockfish, num=5):
    return stockfish.get_top_moves(num)


def get_best_move(stockfish):
    return stockfish.get_best_move()
