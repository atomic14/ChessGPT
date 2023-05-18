from .board_svg import board
from .fen import get_fen
from .levels import get_levels
from .move import make_move
from .move_history import get_move_history
from .new_game import new_game

# TODO - rationalise this
from .static import (
    serve_openai_yaml,
    index,
    site_manifest,
    send_image,
    serve_logo,
    serve_robots,
    serve_favicon,
)

__all__ = [
    "board",
    "get_fen",
    "get_levels",
    "get_move_history",
    "make_move",
    "new_game",
    "serve_openai_yaml",
    "index",
    "site_manifest",
    "send_image",
    "serve_logo",
    "serve_robots",
    "serve_favicon",
]
