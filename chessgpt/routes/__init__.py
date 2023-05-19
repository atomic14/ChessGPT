from .board_svg import board_routes
from .fen import get_fen_routes
from .levels import get_levels_routes
from .move import make_move_routes
from .move_history import get_move_history_routes
from .new_game import new_game_routes
from .static import static_routes

__all__ = [
    "board_routes",
    "get_fen_routes",
    "get_levels_routes",
    "get_move_history_routes",
    "make_move_routes",
    "new_game_routes",
    "static_routes",
]
