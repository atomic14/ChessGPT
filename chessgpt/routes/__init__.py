from .board_svg import board
from .fen import get_fen
from .levels import get_levels
from .move import make_move
from .move_history import get_move_history
from .new_game import new_game
from .static import static_routes

__all__ = [
    "board",
    "get_fen",
    "get_levels",
    "get_move_history",
    "make_move",
    "new_game",
    "static_routes",
]
