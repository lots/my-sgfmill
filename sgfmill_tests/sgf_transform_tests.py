"""Tests for sgf_transform.py."""

from . import sgfmill_test_support

from sgfmill import sgf
from sgfmill import sgf_transform
from sgfmill.common import format_vertex

def make_tests(suite):
    suite.addTests(sgfmill_test_support.make_simple_tests(globals()))


def test_transform_point(tc):
    # The documented mapping, on a 9x9 board, in sgfmill's (row, col) terms,
    # where (0, 0) is the bottom left (A1).
    tc.assertEqual(sgf_transform.transform_point((0, 0), sgf_transform.FLIP_VERTICAL, 9), (8, 0))
    tc.assertEqual(sgf_transform.transform_point((0, 0), sgf_transform.FLIP_HORIZONTAL, 9), (0, 8))
    # A clockwise turn carries the bottom left corner up the left edge, and
    # an anticlockwise one carries it along the bottom edge.
    tc.assertEqual(sgf_transform.transform_point((0, 0), sgf_transform.ROTATE_CW, 9), (8, 0))
    tc.assertEqual(sgf_transform.transform_point((0, 0), sgf_transform.ROTATE_ACW, 9), (0, 8))
    # Stated in display terms as well, because that is what a viewer sees: the
    # top left corner (row 8, col 0) goes to the top right (row 8, col 8) when
    # the board is turned clockwise.
    tc.assertEqual(sgf_transform.transform_point((8, 0), sgf_transform.ROTATE_CW, 9), (8, 8))
    tc.assertEqual(sgf_transform.transform_point((8, 0), sgf_transform.ROTATE_ACW, 9), (0, 0))
    # A pass has no position
    tc.assertIs(sgf_transform.transform_point(None, sgf_transform.ROTATE_CW, 9), None)
    tc.assertRaises(ValueError, sgf_transform.transform_point,
                    (0, 0), "sideways", 9)

def test_single_stone_geometry(tc):
    # One black stone at A9 (the top left). Read back as a vertex name, so that
    # the test is stated in the same terms a user would see.
    def transformed(transformation):
        sgf_game = sgf.Sgf_game.from_bytes(b"(;FF[4]GM[1]SZ[9]AB[aa])")
        tc.assertEqual(sgf_game.get_root().get("AB"), {(8, 0)})
        sgf_transform.transform_game(sgf_game, transformation)
        return format_vertex(sgf_game.get_root().get("AB").pop())
    tc.assertEqual(transformed(sgf_transform.FLIP_VERTICAL), "A1")
    tc.assertEqual(transformed(sgf_transform.FLIP_HORIZONTAL), "J9")
    # A clockwise turn carries the top left corner to the top right; an
    # anticlockwise one carries it to the bottom left.
    tc.assertEqual(transformed(sgf_transform.ROTATE_CW), "J9")
    tc.assertEqual(transformed(sgf_transform.ROTATE_ACW), "A1")

def test_corner_cycle(tc):
    # Turning a corner clockwise should walk it round the corners. SGF 'aa' is
    # the top-left corner, A9; turning clockwise takes it to J9, then J1, A1,
    # and back to A9.
    sgf_game = sgf.Sgf_game.from_bytes(b"(;FF[4]GM[1]SZ[9]AB[aa])")
    seen = []
    for _ in range(5):
        seen.append(format_vertex(list(sgf_game.get_root().get("AB"))[0]))
        sgf_transform.transform_game(sgf_game, sgf_transform.ROTATE_CW)
    tc.assertEqual(seen, ["A9", "J9", "J1", "A1", "A9"])

def test_involutions(tc):
    source = (b"(;FF[4]GM[1]SZ[9]AB[aa][cc][gg]AW[ee]CR[fg]TR[cd]"
              b"LB[gg:A]AR[cc:ee]LN[dd:ff]TB[hh]VW[]DD[];B[ee];W[ff])")
    # Either flip, applied twice, is the identity...
    for transformation in (sgf_transform.FLIP_VERTICAL,
                           sgf_transform.FLIP_HORIZONTAL):
        sgf_game = sgf.Sgf_game.from_bytes(source)
        sgf_transform.transform_game(sgf_game, transformation)
        sgf_transform.transform_game(sgf_game, transformation)
        tc.assertEqual(sgf_game.serialise(),
                       sgf.Sgf_game.from_bytes(source).serialise())
    # ...as is a quarter-turn applied four times.
    sgf_game = sgf.Sgf_game.from_bytes(source)
    for _ in range(4):
        sgf_transform.transform_game(sgf_game, sgf_transform.ROTATE_CW)
    tc.assertEqual(sgf_game.serialise(),
                   sgf.Sgf_game.from_bytes(source).serialise())
    # A clockwise turn undone by an anti-clockwise one.
    sgf_game = sgf.Sgf_game.from_bytes(source)
    sgf_transform.transform_game(sgf_game, sgf_transform.ROTATE_CW)
    sgf_transform.transform_game(sgf_game, sgf_transform.ROTATE_ACW)
    tc.assertEqual(sgf_game.serialise(),
                   sgf.Sgf_game.from_bytes(source).serialise())
    # Two clockwise turns equal one vertical and one horizontal flip.
    a = sgf.Sgf_game.from_bytes(source)
    for _ in range(2):
        sgf_transform.transform_game(a, sgf_transform.ROTATE_CW)
    b = sgf.Sgf_game.from_bytes(source)
    sgf_transform.transform_game(b, sgf_transform.FLIP_VERTICAL)
    sgf_transform.transform_game(b, sgf_transform.FLIP_HORIZONTAL)
    tc.assertEqual(a.serialise(), b.serialise())

def test_transform_markup(tc):
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[19]CR[aa]SQ[bb]MA[cc]TR[dd]SL[ee]"
        b"LB[aa:label]AR[aa:bb]LN[cc:dd]TB[ff]TW[gg]VW[hh]DD[ii])")
    root = sgf_game.get_root()
    # SGF 'aa' is the top left, (size-1, 0). The label's text doesn't move.
    tc.assertEqual(root.get("CR"), {(18, 0)})
    tc.assertEqual(root.get("SQ"), {(17, 1)})
    tc.assertEqual(root.get("LB"), [((18, 0), "label")])
    tc.assertEqual(root.get("AR"), [((18, 0), (17, 1))])
    sgf_transform.transform_game(sgf_game, sgf_transform.FLIP_VERTICAL)
    tc.assertEqual(root.get("CR"), {(0, 0)})
    tc.assertEqual(root.get("SQ"), {(1, 1)})
    tc.assertEqual(root.get("MA"), {(2, 2)})
    tc.assertEqual(root.get("TR"), {(3, 3)})
    tc.assertEqual(root.get("SL"), {(4, 4)})
    tc.assertEqual(root.get("TB"), {(5, 5)})
    tc.assertEqual(root.get("TW"), {(6, 6)})
    tc.assertEqual(root.get("VW"), {(7, 7)})
    tc.assertEqual(root.get("DD"), {(8, 8)})
    # A label's point moves, but its text does not
    tc.assertEqual(root.get("LB"), [((0, 0), "label")])
    # An arrow's two points both move, and their order is kept
    tc.assertEqual(root.get("AR"), [((0, 0), (1, 1))])
    tc.assertEqual(root.get("LN"), [((2, 2), (3, 3))])

def test_transform_whole_tree(tc):
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[9];B[aa](;W[bb]CR[cc])(;W[dd]TR[ee](;B[ff]SQ[gg])))")
    sgf_transform.transform_game(sgf_game, sgf_transform.ROTATE_CW)
    root = sgf_game.get_root()
    # A clockwise turn on a 9x9 board: (row, col) -> (8-col, row), so the top
    # left corner ends up at the top right.
    tc.assertEqual(root[0].get_move(), ("b", (8, 8)))
    tc.assertEqual(root[0][0].get_move(), ("w", (7, 7)))
    tc.assertEqual(root[0][0].get("CR"), {(6, 6)})
    tc.assertEqual(root[0][1].get_move(), ("w", (5, 5)))
    tc.assertEqual(root[0][1].get("TR"), {(4, 4)})
    tc.assertEqual(root[0][1][0].get_move(), ("b", (3, 3)))
    tc.assertEqual(root[0][1][0].get("SQ"), {(2, 2)})

def test_transform_preserves_other_properties(tc):
    source = (b"(;FF[4]GM[1]CA[UTF-8]SZ[9]PB[Black]PW[White]"
              b"RE[B+R]KM[5.5]C[comment];B[aa]N[node]BL[12.5])")
    sgf_game = sgf.Sgf_game.from_bytes(source)
    sgf_transform.transform_game(sgf_game, sgf_transform.ROTATE_CW)
    root = sgf_game.get_root()
    tc.assertEqual(root.get("PB"), "Black")
    tc.assertEqual(root.get("PW"), "White")
    tc.assertEqual(root.get("RE"), "B+R")
    tc.assertEqual(root.get("KM"), 5.5)
    tc.assertEqual(root.get("C"), "comment")
    tc.assertEqual(root.get("SZ"), 9)
    tc.assertEqual(root[0].get("N"), "node")
    tc.assertEqual(root[0].get("BL"), 12.5)
    # A clockwise turn: (row, col) -> (8-col, row)
    tc.assertEqual(root[0].get_move(), ("b", (8, 8)))

def test_transform_rectangular_list_items(tc):
    # AR and LN values are lists of pairs; the pairs themselves must not be
    # reordered or merged.
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[9]AR[aa:bb][cc:dd]LN[ee:ff])")
    root = sgf_game.get_root()
    tc.assertEqual(root.get("AR"), [((8, 0), (7, 1)), ((6, 2), (5, 3))])
    tc.assertEqual(root.get("LN"), [((4, 4), (3, 5))])
    sgf_transform.transform_game(sgf_game, sgf_transform.FLIP_VERTICAL)
    # The pairs are transformed independently, and their order is kept.
    tc.assertEqual(root.get("AR"), [((0, 0), (1, 1)), ((2, 2), (3, 3))])
    tc.assertEqual(root.get("LN"), [((4, 4), (5, 5))])

def test_transform_game_errors(tc):
    sgf_game = sgf.Sgf_game.from_bytes(b"(;FF[4]GM[1]SZ[9];B[aa])")
    tc.assertRaises(ValueError, sgf_transform.transform_game, sgf_game, "turn")
    # A failed call shouldn't have changed anything
    tc.assertEqual(sgf_game.serialise(), b"(;FF[4]GM[1]SZ[9];B[aa])\n")

def test_transformations_constant(tc):
    tc.assertEqual(set(sgf_transform.TRANSFORMATIONS),
                   set(["flip_vertical", "flip_horizontal",
                        "rotate_cw", "rotate_acw"]))
