"""Tests for sgf_encoding.py."""

from . import sgfmill_test_support

from sgfmill import sgf
from sgfmill import sgf_encoding

def make_tests(suite):
    suite.addTests(sgfmill_test_support.make_simple_tests(globals()))


def _comment(data):
    """Return the C property of the first node, read as UTF-8."""
    return sgf.Sgf_game.from_bytes(data).get_root().get("C")


def test_detect_utf8(tc):
    result = sgf_encoding.detect_bytes(
        "(;FF[4]CA[UTF-8]C[résumé])".encode("utf-8"))
    tc.assertEqual(result.encoding, "UTF-8")
    tc.assertEqual(result.declared, "UTF-8")
    tc.assertFalse(result.mismatch)
    tc.assertFalse(result.ascii_only)
    tc.assertFalse(result.needs_conversion())
    tc.assertEqual(result.game().get_root().get("C"), "résumé")
    tc.assertEqual(str(result), "UTF-8")

def test_detect_utf8_bom(tc):
    # A byte order mark settles the encoding, whatever CA says.
    data = (b"\xef\xbb\xbf"
            + "(;FF[4]CA[ISO-8859-1]C[résumé])".encode("utf-8"))
    result = sgf_encoding.detect_bytes(data)
    tc.assertEqual(result.encoding, "UTF-8")
    tc.assertEqual(result.game().get_root().get("C"), "résumé")

def test_detect_undeclared_utf8(tc):
    # No CA property: UTF-8 is tried before ISO-8859-1.
    result = sgf_encoding.detect_bytes("(;FF[4]C[résumé])".encode("utf-8"))
    tc.assertEqual(result.encoding, "UTF-8")
    tc.assertIs(result.declared, None)
    tc.assertTrue(result.mismatch)
    # Already UTF-8, so there is nothing to convert.
    tc.assertFalse(result.needs_conversion())
    tc.assertEqual(result.game().get_root().get("C"), "résumé")
    tc.assertEqual(str(result), "UTF-8 (no CA property)")

def test_detect_latin1(tc):
    for data in ("(;FF[4]CA[ISO-8859-1]C[résumé])".encode("iso-8859-1"),
                 "(;FF[4]C[résumé])".encode("iso-8859-1")):
        result = sgf_encoding.detect_bytes(data)
        tc.assertEqual(result.encoding, "ISO-8859-1")
        tc.assertTrue(result.needs_conversion())
        tc.assertEqual(result.game().get_root().get("C"), "résumé")

def test_detect_declared_latin1_with_utf8_bytes(tc):
    # A file that declares an encoding which is wrong but which still decodes
    # its bytes. There is no way to tell, so the declaration is followed, and
    # the mismatch is reported rather than silently corrected.
    data = "(;FF[4]CA[ISO-8859-1]C[résumé])".encode("utf-8")
    result = sgf_encoding.detect_bytes(data)
    tc.assertEqual(result.encoding, "ISO-8859-1")
    tc.assertEqual(result.declared, "ISO-8859-1")
    tc.assertFalse(result.mismatch)
    tc.assertEqual(result.game().get_root().get("C"), "rÃ©sumÃ©")
    # The caller can override it.
    converted = sgf_encoding.convert_game_to_utf8(result.game(),
                                                  encoding="UTF-8")
    tc.assertEqual(_comment(converted), "résumé")

def test_detect_declared_not_a_codec(tc):
    # A CA property naming something Python doesn't know must not stop the
    # data being read.
    data = "(;FF[4]CA[BOGUS-99]C[résumé])".encode("utf-8")
    result = sgf_encoding.detect_bytes(data)
    tc.assertEqual(result.encoding, "UTF-8")
    tc.assertEqual(result.declared, "BOGUS-99")
    tc.assertTrue(result.mismatch)
    tc.assertEqual(result.game().get_root().get("C"), "résumé")

def test_detect_declared_wrong_and_not_utf8(tc):
    # Declared UTF-8, but the bytes are not.
    data = "(;FF[4]CA[UTF-8]C[résumé])".encode("iso-8859-1")
    result = sgf_encoding.detect_bytes(data)
    tc.assertEqual(result.encoding, "ISO-8859-1")
    tc.assertEqual(result.declared, "UTF-8")
    tc.assertTrue(result.mismatch)
    tc.assertEqual(result.game().get_root().get("C"), "résumé")

def test_detect_gb2312(tc):
    data = "(;FF[4]CA[GB2312]C[你好])".encode("gb2312")
    result = sgf_encoding.detect_bytes(data)
    tc.assertEqual(result.encoding, "GB2312")
    tc.assertEqual(result.game().get_root().get("C"), "你好")

def test_detect_ascii_only(tc):
    # No non-ASCII bytes: nothing to convert, and the declaration is kept.
    result = sgf_encoding.detect_bytes(b"(;FF[4]CA[ISO-8859-1]C[hello])")
    tc.assertEqual(result.encoding, "ISO-8859-1")
    tc.assertTrue(result.ascii_only)
    tc.assertTrue(result.needs_conversion())
    tc.assertEqual(result.game().get_root().get("C"), "hello")
    # Without a CA property, UTF-8 is assumed.
    result = sgf_encoding.detect_bytes(b"(;FF[4]C[hello])")
    tc.assertEqual(result.encoding, "UTF-8")
    tc.assertIs(result.declared, None)

def test_detect_bytes_errors(tc):
    tc.assertRaises(sgf_encoding.SgfEncodingError,
                    sgf_encoding.detect_bytes, b"not sgf data")
    tc.assertRaises(sgf_encoding.SgfEncodingError,
                    sgf_encoding.detect_bytes, b"")

def test_detect_game(tc):
    # detect_game() cannot see the original bytes, so it reports the
    # declaration.
    sgf_game = sgf.Sgf_game.from_bytes(b"(;FF[4]CA[ISO-8859-1]C[hello])")
    result = sgf_encoding.detect_game(sgf_game)
    tc.assertEqual(result.encoding, "ISO-8859-1")
    tc.assertEqual(result.declared, "ISO-8859-1")
    tc.assertFalse(result.mismatch)
    # A game with no CA property reports the specification's default.
    sgf_game = sgf.Sgf_game.from_bytes(b"(;FF[4]C[hello])")
    tc.assertEqual(sgf_encoding.detect_game(sgf_game).encoding,
                   "ISO-8859-1")

def test_convert_to_utf8(tc):
    data = "(;FF[4]CA[ISO-8859-1]C[résumé]PB[player])".encode("iso-8859-1")
    result = sgf_encoding.detect_bytes(data)
    converted = sgf_encoding.convert_game_to_utf8(result.game())
    tc.assertEqual(_comment(converted), "résumé")
    # The output declares UTF-8...
    tc.assertIn(b"CA[UTF-8]", converted)
    # ...and is really UTF-8.
    tc.assertEqual(converted, converted.decode("utf-8").encode("utf-8"))
    # Converting again changes nothing.
    again = sgf_encoding.convert_game_to_utf8(
        sgf_encoding.detect_bytes(converted).game())
    tc.assertEqual(again, converted)

def test_convert_already_utf8(tc):
    data = "(;FF[4]CA[UTF-8]C[résumé])".encode("utf-8")
    result = sgf_encoding.detect_bytes(data)
    tc.assertFalse(result.needs_conversion())
    converted = sgf_encoding.convert_game_to_utf8(result.game())
    # The text is unchanged (serialising reorders properties and adds a
    # trailing newline, so compare the content, not the bytes).
    tc.assertEqual(_comment(converted), "résumé")
    tc.assertIn(b"CA[UTF-8]", converted)

def test_convert_variations(tc):
    # Every node of the tree should be converted, including variations.
    source = ("(;FF[4]CA[ISO-8859-1]C[résumé];B[cc]"
              "(;W[dd]N[naïve])(;W[ee]C[Grün]))")
    data = source.encode("iso-8859-1")
    converted = sgf_encoding.convert_game_to_utf8(
        sgf_encoding.detect_bytes(data).game())
    # Compare the parsed result, so that property ordering doesn't matter.
    before = sgf.Sgf_game.from_bytes(source.encode("utf-8"))
    after = sgf.Sgf_game.from_bytes(converted)
    tc.assertEqual(after.get_root().get("C"), "résumé")
    tc.assertEqual(after.get_root().get("CA"), "UTF-8")
    tc.assertEqual(after.get_root()[0][0].get("N"), "naïve")
    tc.assertEqual(after.get_root()[0][1].get("C"), "Grün")
    # The trees have the same shape and the same moves.
    tc.assertEqual(len(after.get_root()[0]), len(before.get_root()[0]))
    tc.assertEqual(after.get_root()[0][0].get_move(), ("w", (15, 3)))

def test_convert_non_latin_text(tc):
    # Text which isn't Latin-1, so the source encoding has to be honoured.
    source = "(;FF[4]CA[GB2312]C[你好];B[cc];W[dd]C[围棋])"
    data = source.encode("gb2312")
    result = sgf_encoding.detect_bytes(data)
    tc.assertEqual(result.encoding, "GB2312")
    converted = sgf_encoding.convert_game_to_utf8(result.game())
    after = sgf.Sgf_game.from_bytes(converted)
    tc.assertEqual(after.get_root().get("C"), "你好")
    tc.assertEqual(after.get_root().get("CA"), "UTF-8")
    tc.assertEqual(after.get_root()[0][0].get("C"), "围棋")
    # The bytes really are UTF-8.
    tc.assertEqual(converted, converted.decode("utf-8").encode("utf-8"))
    tc.assertIn("围棋".encode("utf-8"), converted)

def test_convert_with_declared_wrong(tc):
    # The declared encoding says Latin-1, but the bytes are UTF-8.
    data = "(;FF[4]CA[ISO-8859-1]C[résumé])".encode("utf-8")
    result = sgf_encoding.detect_bytes(data)
    converted = sgf_encoding.convert_game_to_utf8(result.game(),
                                                  encoding="UTF-8")
    tc.assertEqual(_comment(converted), "résumé")

def test_convert_errors(tc):
    tc.assertRaises(sgf_encoding.SgfEncodingError,
                    sgf_encoding._game_from_bytes, b"(;FF[4])", "NO-SUCH-CODEC")
    tc.assertRaises(sgf_encoding.SgfEncodingError,
                    sgf_encoding._game_from_bytes, b"not sgf", "UTF-8")

def test_encoding_attributes(tc):
    result = sgf_encoding.detect_bytes(
        "(;FF[4]CA[UTF-8]C[résumé])".encode("utf-8"))
    tc.assertEqual(repr(result).startswith("<Sgf_encoding: "), True)
    tc.assertEqual(sgf_encoding.UTF8, "UTF-8")
