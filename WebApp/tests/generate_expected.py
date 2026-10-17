"""Generate the expected answers for the web app's tests, using sgfmill.

The web app is a JavaScript port of this library, so the only trustworthy way
to check it is to ask the library itself what each fixture means and compare.
This script writes fixtures/ and expected.json; run the Node tests afterwards.

    python WebApp/tests/generate_expected.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from sgfmill import (ascii_boards, boards, sgf, sgf_encoding, sgf_moves,
                     sgf_normalise, sgf_transform)

FIXTURES = os.path.join(HERE, "fixtures")

# Games written as text. They are deliberately ASCII so that the comparison of
# serialised output is unambiguous; the encoding fixtures below are written as
# bytes instead, and only their detection results are compared.
GAMES = {
    "simple.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]PB[Black]PW[White]KM[6.5]"
        ";B[cg];W[gc];B[gg])"
    ),
    "variations.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]PB[Black]"
        ";B[cg](;W[gc];B[gg])(;W[cc];B[gg];W[ee]))"
    ),
    "setup.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]AB[aa][ia]AW[ii][ai]AE[ee]HA[2]"
        ";B[cg];W[gc])"
    ),
    "markup.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]CR[aa][bb]MA[cc]TR[dd]SQ[ee]SL[ff]"
        "LB[aa:top-left][gg:label]AR[aa:bb]LN[cc:dd]TB[hh]TW[ii]VW[cc]DD[]"
        ";B[ee])"
    ),
    "nonstandard.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]MULTIGOGM[1]CM[some comment]"
        "PB[Black]XX[custom];B[cg]YY[node custom];W[gc])"
    ),
    "pass.sgf": "(;FF[4]GM[1]CA[UTF-8]SZ[9];B[cg];W[];B[gc];W[tt])",
    "big19.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[19]PB[Black]PW[White]KM[7.5]"
        ";B[pd];W[dp];B[pp];W[dd];B[fq];W[cn];B[jp];W[qn])"
    ),
    "collection.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]GN[first];B[cg])"
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]GN[second];B[gg];W[cc])"
    ),
    "compressed.sgf": (
        # Compressed point lists ('aa:cc' means the whole rectangle), which
        # FF[4] allows and real files use, plus a duplicate point that should
        # merge rather than appear twice.
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]AB[aa:bc][cc]AW[ee:gg]CR[bb:cc]"
        "TB[ab:ac]TW[ii]DD[hh:hi]VW[de:df]LB[aa:Rect];B[ii])"
    ),
    "comment.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]C[a comment with a \\] bracket and a "
        "\\\\ backslash];B[cg]C[node comment])"
    ),
}

# (name, bytes) for the encoding cases.
ENCODINGS = {
    "enc-utf8.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]PB[Black]C[caf\u00e9 \u4e2d\u6587];B[cg])"
    ).encode("utf-8"),
    "enc-utf8-bom.sgf": b"\xef\xbb\xbf" + (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]C[caf\u00e9];B[cg])"
    ).encode("utf-8"),
    "enc-latin1-declared.sgf": (
        "(;FF[4]GM[1]CA[ISO-8859-1]SZ[9]C[caf\u00e9];B[cg])"
    ).encode("iso-8859-1"),
    "enc-latin1-undeclared.sgf": (
        "(;FF[4]GM[1]SZ[9]C[caf\u00e9];B[cg])"
    ).encode("iso-8859-1"),
    "enc-ascii-ca.sgf": (
        "(;FF[4]GM[1]CA[ISO-8859-1]SZ[9]C[plain ascii];B[cg])"
    ).encode("ascii"),
    "enc-mismatch.sgf": (
        "(;FF[4]GM[1]CA[UTF-8]SZ[9]C[caf\u00e9];B[cg])"
    ).encode("iso-8859-1"),
}


def walk(node):
    yield node
    for child in node:
        yield from walk(child)


def points(game, values):
    """Point sets as sorted "row,col" strings, so JSON stays simple."""
    return sorted("%d,%d" % (row, col) for row, col in values)


def position_for_node(node):
    """The position a node leads to, following its ancestors."""
    chain = []
    current = node
    while current is not None:
        chain.append(current)
        current = current.parent
    chain.reverse()
    side = chain[0].owner.get_size()
    board = boards.Board(side)
    board.apply_setup(*chain[0].get_setup_stones())
    for ancestor in chain[1:]:
        board.apply_setup(*ancestor.get_setup_stones())
        colour, move = ancestor.get_move()
        if move is None:
            continue
        try:
            board.play(move[0], move[1], colour)
        except ValueError:
            break
    occupied = board.list_occupied_points()
    return {
        "black": points(None, [p for c, p in occupied if c == "b"]),
        "white": points(None, [p for c, p in occupied if c == "w"]),
    }


def describe_game(text):
    """Everything the web app claims to know about one game."""
    game = sgf.Sgf_game.from_bytes(text.encode("utf-8"))
    board, plays = sgf_moves.get_setup_and_moves(game)
    black, white, empty = game.get_root().get_setup_stones()

    transforms = {}
    for name, transformation in (
            ("flip_vertical", sgf_transform.FLIP_VERTICAL),
            ("flip_horizontal", sgf_transform.FLIP_HORIZONTAL),
            ("rotate_cw", sgf_transform.ROTATE_CW),
            ("rotate_acw", sgf_transform.ROTATE_ACW)):
        copy_bytes = game.serialise()
        copy = sgf.Sgf_game.from_bytes(copy_bytes)
        sgf_transform.transform_game(copy, transformation)
        transforms[name] = copy.serialise().decode("utf-8")

    report = sgf_normalise.check_game(game)
    cleaned = sgf.Sgf_game.from_bytes(game.serialise())
    clean_report = sgf_normalise.clean_game(cleaned)

    # Positions after each move, as the app draws them.
    positions = []
    final_diagram = None
    for limit in range(len(plays) + 1):
        board_at, _ = sgf_moves.get_setup_and_moves(game)
        for colour, move in plays[:limit]:
            if move is None:
                continue
            try:
                board_at.play(move[0], move[1], colour)
            except ValueError:
                break
        occupied = board_at.list_occupied_points()
        positions.append({
            "black": points(game, [p for c, p in occupied if c == "b"]),
            "white": points(game, [p for c, p in occupied if c == "w"]),
        })
        if limit == len(plays):
            final_diagram = ascii_boards.render_board(board_at)

    return {
        "size": game.get_size(),
        "serialise": game.serialise().decode("utf-8"),
        "nodeCount": sum(1 for _ in walk(game.get_root())),
        "mainLineCount": len(game.get_main_sequence()),
        "plays": [[colour, None if move is None else [move[0], move[1]]]
                  for colour, move in plays],
        "setup": {"black": points(game, black), "white": points(game, white),
                  "empty": points(game, empty)},
        "positions": positions,
        "check": {
            "properties": report.properties(),
            "nodeCount": len(report.nodes()),
        },
        "nodePositions": [position_for_node(node)
                          for node in walk(game.get_root())],
        "diagram": final_diagram,
        "clean": {
            "properties": clean_report.properties(),
            "serialise": cleaned.serialise().decode("utf-8"),
        },
        "transforms": transforms,
    }


def describe_encoding(raw):
    result = sgf_encoding.detect_bytes(raw)
    return {
        "encoding": result.encoding,
        "declared": result.declared,
        "mismatch": bool(result.mismatch),
        "asciiOnly": bool(result.ascii_only),
    }


def main():
    os.makedirs(FIXTURES, exist_ok=True)
    expected = {"games": {}, "encodings": {}}

    for name, text in GAMES.items():
        path = os.path.join(FIXTURES, name)
        with open(path, "wb") as f:
            f.write(text.encode("utf-8"))
        expected["games"][name] = describe_game(text)

    for name, raw in ENCODINGS.items():
        path = os.path.join(FIXTURES, name)
        with open(path, "wb") as f:
            f.write(raw)
        expected["encodings"][name] = describe_encoding(raw)

    out = os.path.join(HERE, "expected.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=1, sort_keys=True)
        f.write("\n")

    print("wrote %d game fixtures and %d encoding fixtures"
          % (len(GAMES), len(ENCODINGS)))
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
