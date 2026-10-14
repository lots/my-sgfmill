"""Tests for sgf_normalise.py."""

from . import sgfmill_test_support

from sgfmill import sgf
from sgfmill import sgf_normalise
from sgfmill import sgf_properties

def make_tests(suite):
    suite.addTests(sgfmill_test_support.make_simple_tests(globals()))


def test_standard_properties(tc):
    # Every standard property should be one the library knows a type for,
    # except the three FF[4] properties it deliberately has no type for.
    known = set(sgf_properties._property_types_by_ident)
    untyped = set(["ID", "L", "LT"])
    tc.assertEqual(sgf_normalise.STANDARD_PROPERTIES - known, untyped)
    # And every typed property should be standard: sgfmill implements the
    # general FF[4] properties and the Go-specific ones.
    tc.assertEqual(known - sgf_normalise.STANDARD_PROPERTIES, set())

def test_minimum_standard_properties(tc):
    tc.assertEqual(sgf_normalise.MINIMUM_STANDARD_PROPERTIES,
                   set(["FF", "GM", "SZ"]))

def test_check_game(tc):
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[9]XX[hello]YY[1][2];B[cc]XX[again])")
    report = sgf_normalise.check_game(sgf_game)
    tc.assertEqual(report.properties(), ["XX", "YY"])
    tc.assertEqual(len(report), 2)
    tc.assertTrue(report)
    tc.assertFalse(report.removed)
    tc.assertEqual(len(report.nodes()), 2)
    tc.assertEqual(str(report), "Non-standard properties: XX, YY")
    # check_game() doesn't modify the game
    tc.assertTrue(sgf_game.get_root().has_property("XX"))
    tc.assertTrue(sgf_game.get_root().has_property("YY"))

def test_clean_game(tc):
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[9]XX[hello]YY[1][2];B[cc]XX[again])")
    report = sgf_normalise.clean_game(sgf_game)
    tc.assertEqual(report.properties(), ["XX", "YY"])
    tc.assertTrue(report.removed)
    tc.assertEqual(str(report), "Removed non-standard properties: XX, YY")
    tc.assertFalse(sgf_game.get_root().has_property("XX"))
    tc.assertFalse(sgf_game.get_root().has_property("YY"))
    tc.assertFalse(sgf_game.get_root()[0].has_property("XX"))
    # Standard properties survive
    tc.assertEqual(sgf_game.get_root().get("SZ"), 9)
    tc.assertEqual(sgf_game.get_root()[0].get_move(), ("b", (6, 2)))
    # Nothing left to find
    tc.assertFalse(sgf_normalise.check_game(sgf_game))

def test_clean_variations(tc):
    # The whole tree should be visited, including variations.
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[9];B[cc](;W[dd]AA[1])(;W[ee]BB[2](;B[ff]CC[3])))")
    report = sgf_normalise.check_game(sgf_game)
    tc.assertEqual(report.properties(), ["AA", "BB", "CC"])
    for name in ("AA", "BB", "CC"):
        tc.assertEqual(len(report.findings[name]), 1)
    sgf_normalise.clean_game(sgf_game)
    tc.assertFalse(sgf_normalise.check_game(sgf_game))
    # The tree structure is unchanged
    tc.assertEqual(len(sgf_game.get_root()[0]), 2)
    tc.assertEqual(len(sgf_game.get_root()[0][1]), 1)

def test_clean_custom_standard(tc):
    # A caller can accept their own private properties.
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[9]MULTIGOGM[1]XX[keepme])")
    report = sgf_normalise.clean_game(
        sgf_game, standard=sgf_normalise.STANDARD_PROPERTIES | {"XX"})
    tc.assertEqual(report.properties(), ["MULTIGOGM"])
    tc.assertTrue(sgf_game.get_root().has_property("XX"))
    tc.assertFalse(sgf_game.get_root().has_property("MULTIGOGM"))

def test_clean_nothing_to_do(tc):
    sgf_game = sgf.Sgf_game.from_bytes(b"(;FF[4]GM[1]SZ[9];B[cc])")
    report = sgf_normalise.clean_game(sgf_game)
    tc.assertFalse(report)
    tc.assertEqual(len(report), 0)
    tc.assertEqual(report.properties(), [])
    tc.assertEqual(report.nodes(), [])
    tc.assertEqual(str(report), "No non-standard properties found")
    tc.assertEqual(sgf_game.serialise(), b"(;FF[4]GM[1]SZ[9];B[cc])\n")

def test_clean_preserves_standard_content(tc):
    source = (b"(;FF[4]GM[1]CA[UTF-8]SZ[9]PB[Black]XX[junk]"
              b"C[comment];B[cc]YY[junk];W[dd])")
    sgf_game = sgf.Sgf_game.from_bytes(source)
    sgf_normalise.clean_game(sgf_game)
    tc.assertEqual(sgf_game.serialise(),
                   b"(;FF[4]C[comment]CA[UTF-8]GM[1]PB[Black]SZ[9]"
                   b";B[cc];W[dd])\n")

def test_report_nodes_and_findings(tc):
    # findings maps each identifier to the nodes containing it; nodes() gives
    # the distinct nodes, in tree order.
    sgf_game = sgf.Sgf_game.from_bytes(
        b"(;FF[4]GM[1]SZ[9]AA[1];B[cc]AA[2]BB[3];W[dd]BB[4])")
    report = sgf_normalise.check_game(sgf_game)
    tc.assertEqual(report.properties(), ["AA", "BB"])
    tc.assertEqual([len(v) for v in report.findings.values()], [2, 2])
    nodes = report.nodes()
    tc.assertEqual(len(nodes), 3)
    # in tree order: root, then its children
    tc.assertIs(nodes[0], sgf_game.get_root())
    tc.assertIs(nodes[1], sgf_game.get_root()[0])
    tc.assertIs(nodes[2], sgf_game.get_root()[0][0])
