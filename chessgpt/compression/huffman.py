import base64
import chess

HUFFMAN_DICT = {
    ".": "1",
    "P": "010",
    "p": "001",
    "B": "00010",
    "N": "00000",
    "R": "01110",
    "b": "00011",
    "n": "00001",
    "r": "01101",
    "K": "011110",
    "Q": "011001",
    "k": "011111",
    "q": "011000",
}

REVERSE_HUFFMAN_DICT = {v: k for k, v in HUFFMAN_DICT.items()}


def string_to_bytes(s):
    return int(s, 2).to_bytes((len(s) + 7) // 8, byteorder="big")


def bytes_to_string(b):
    return bin(int.from_bytes(b, byteorder="big"))[2:].zfill(len(b) * 8)


def encode_board(board):
    board_string = str(board).replace(" ", "").replace("\n", "")
    binary_string = "".join(HUFFMAN_DICT[char] for char in board_string)
    # Add padding to the end of the binary string
    padded_binary_string = binary_string.ljust((len(binary_string) + 7) // 8 * 8, "0")
    b = string_to_bytes(padded_binary_string)
    b64 = base64.urlsafe_b64encode(b).decode()
    # strip off the padding
    return b64.rstrip("=")


def decode_board(encoded_board):
    code = ""
    position = 0
    board = chess.Board()
    board.clear()
    # add on the padding
    encoded_board += "=" * (-len(encoded_board) % 4)
    decoded = base64.urlsafe_b64decode(encoded_board.encode())
    for bit in bytes_to_string(decoded):
        code += bit
        if code in REVERSE_HUFFMAN_DICT:
            piece = REVERSE_HUFFMAN_DICT[code]
            if piece != ".":
                x = position % 8
                y = 7 - position // 8
                board.set_piece_at(y * 8 + x, chess.Piece.from_symbol(piece))
            position += 1
            code = ""
            if position == 64:
                break
    return board
