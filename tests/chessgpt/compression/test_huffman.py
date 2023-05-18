import pytest
import chess
from chessgpt.compression.huffman import encode_board, decode_board


def test_encode_and_decode():
    # Arrange
    board = chess.Board()

    # Act
    encoded = encode_board(board)
    decoded = decode_board(encoded)

    # Assert
    assert str(board) == str(decoded)


def test_encode_and_decode_with_moves():
    # Arrange
    board = chess.Board()
    board.push_san("e4")
    board.push_san("e5")
    board.push_san("Qh5")
    board.push_san("Nc6")

    # Act
    encoded = encode_board(board)
    decoded = decode_board(encoded)

    # Assert
    assert str(board) == str(decoded)


def test_decode_invalid_input():
    # Arrange
    invalid_encoded = "This is not valid base 64 XXXX11"

    # Act & Assert
    with pytest.raises(Exception):
        decode_board(invalid_encoded)
