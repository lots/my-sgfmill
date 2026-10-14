"""Detects the character encoding of SGF data, and converts it to UTF-8.

The SGF specification says that Text and SimpleText property values use the
encoding named by the root ``CA`` property, defaulting to ``ISO-8859-1``. In
practice files are often written with an encoding other than the one they
declare, or with no ``CA`` property at all, which makes their comments and
player names display as mojibake.

This module works out the encoding that a file's bytes are actually in, reports
the ``CA`` property, and can rewrite the data as UTF-8.

::

    >>> from sgfmill import sgf_encoding
    >>> result = sgf_encoding.detect_bytes(open("game.sgf", "rb").read())
    >>> print(result)
    UTF-8 (file declares ISO-8859-1)
    >>> if result.needs_conversion():
    ...     data = sgf_encoding.convert_game_to_utf8(result.game())
    ...     open("game-utf8.sgf", "wb").write(data)

How the encoding is worked out
  #. A UTF-8 byte order mark settles it, regardless of the ``CA`` property.

  #. Otherwise the ``CA`` property is read. If it names a Python codec, and
     every Text and SimpleText value can be decoded with it, that encoding is
     used: a file that says what it is, is believed.

  #. Otherwise the bytes are tested against ``UTF-8``, which is the usual
     intent. UTF-8 is quite hard to satisfy by accident, so this is a reliable
     signal.

  #. Otherwise ``ISO-8859-1`` is used, as it can decode any byte sequence at
     all. It therefore never fails, but it may well be wrong: with no better
     evidence there is no way to distinguish, for example, Latin-1 from
     CP1252.

  Step 2 is skipped for files containing no non-ASCII bytes, because every
  ASCII-compatible encoding decodes those identically; such a file doesn't need
  converting, and the declared encoding is reported.

  What this cannot do is notice a file that declares an encoding which is
  wrong but which still decodes its bytes. A UTF-8 file labelled
  ``CA[ISO-8859-1]`` is ambiguous: those bytes form a valid Latin-1 string too,
  just not the intended one. Detection therefore follows the declaration, and
  the mismatch is reported rather than silently corrected. Pass
  ``encoding="UTF-8"`` to :func:`convert_game_to_utf8` to override this.

  Only properties that the library knows to be of Text or SimpleText type are
  examined, and (when converting) re-encoded. A private property holding text
  isn't detected, and its bytes are left as they are.

Multi-game files
  These functions work on a single game. For a collection, split it first (see
  :mod:`sgfmill.sgf_grammar`), or apply them to each game in turn.

Board size and other properties are not affected.
"""

import codecs

from . import sgf
from . import sgf_grammar
from . import sgf_properties


__all__ = [
    "UTF8",
    "Sgf_encoding",
    "SgfEncodingError",
    "detect_bytes",
    "detect_game",
    "convert_game_to_utf8",
]


#: The encoding converted files are written in.
UTF8 = "UTF-8"


class SgfEncodingError(Exception):
    """Raised when an SGF file's encoding can't be determined or converted."""


# The property identifiers whose type is Text or SimpleText, taken from the
# library's own table so that they stay in step with it.
_text_identifiers = frozenset(
    identifier
    for identifier, property_type in
        sgf_properties._property_types_by_ident.items()
    if property_type.interpreter.__name__ in
        ("interpret_text", "interpret_simpletext"))


def _walk_nodes(node):
    """Yield 'node' and all its descendants, in tree order (depth first)."""
    yield node
    for child in node:
        yield from _walk_nodes(child)


def _text_values(game):
    """Iterate over the interpreted Text and SimpleText values of a game.

    game -- Sgf_game

    Yields strings. Raises UnicodeDecodeError if a value can't be decoded with
    the game's raw property encoding.

    """
    for node in _walk_nodes(game.get_root()):
        for identifier in sorted(node.get_raw_property_map()):
            if identifier not in _text_identifiers:
                continue
            value = node.get(identifier)
            if isinstance(value, str):
                yield value
            elif isinstance(value, (list, tuple)):
                yield from (v for v in value if isinstance(v, str))


def _declared_charset(bb):
    """Return the encoding named by the CA property, or None.

    This reads the raw parse tree, so unlike Sgf_game.get_charset() it works
    even when the CA property names an encoding that Python doesn't know (in
    which case the name is returned as it appears in the file, unnormalised).

    """
    try:
        coarse = sgf_grammar.parse_sgf_game(bb)
    except ValueError:
        return None
    try:
        raw = coarse.sequence[0]["CA"][0]
    except (IndexError, KeyError):
        return None
    return raw.decode("ascii", "replace")


def _check_encoding(bb, encoding):
    """Return whether the data's text values can be read using 'encoding'.

    Returns a pair (ok, error_message).

    """
    try:
        game = sgf.Sgf_game.from_bytes(bb, override_encoding=encoding)
    except (ValueError, LookupError) as e:
        return False, str(e)
    try:
        for _ in _text_values(game):
            pass
    except UnicodeDecodeError as e:
        return False, str(e)
    return True, None


def _game_from_bytes(bb, encoding):
    """Parse SGF data, forcing the encoding used for its text values."""
    try:
        return sgf.Sgf_game.from_bytes(bb, override_encoding=encoding)
    except (ValueError, LookupError) as e:
        raise SgfEncodingError(str(e)) from None


class Sgf_encoding:
    """The result of examining an SGF file's character encoding.

    Public attributes (treat as read-only):
      encoding   -- the encoding the data is in (a name for a Python codec)
      declared   -- the encoding named by the CA property, or None if there
                    is no CA property
      mismatch   -- True if 'encoding' differs from 'declared'
      ascii_only -- True if the data contains no non-ASCII bytes

    'encoding' and 'declared' are in the normalised form used elsewhere in
    Sgfmill (eg "UTF-8", "ISO-8859-1").

    """
    def __init__(self, encoding, declared, mismatch, ascii_only, data):
        self.encoding = encoding
        self.declared = declared
        self.mismatch = mismatch
        self.ascii_only = ascii_only
        self._data = data

    def needs_conversion(self):
        """Return whether the data would be changed by a conversion to UTF-8.

        This is True if the detected encoding isn't already UTF-8. Data that
        is ASCII-only doesn't need converting, even if it declares another
        encoding, because the bytes are the same either way.

        """
        return self.encoding != UTF8

    def game(self):
        """Return an Sgf_game for the data, using the detected encoding.

        Returns an sgf.Sgf_game whose raw property encoding, and CA property,
        are the detected encoding.

        Raises SgfEncodingError if the data can't be parsed, or if the detected
        encoding can't be used as a Python codec.

        """
        return _game_from_bytes(self._data, self.encoding)

    def __str__(self):
        if self.declared is None:
            return "%s (no CA property)" % self.encoding
        if self.declared == self.encoding:
            return self.encoding
        return "%s (file declares %s)" % (self.encoding, self.declared)

    def __repr__(self):
        return "<Sgf_encoding: %s>" % self


def detect_bytes(bb):
    """Work out the character encoding of some SGF data.

    bb -- bytes-like object (the contents of an SGF file)

    Returns an Sgf_encoding.

    Raises SgfEncodingError if the data can't be parsed at all.

    See the module documentation for how the encoding is chosen.

    """
    if bb[:3] == codecs.BOM_UTF8:
        # An explicit byte order mark settles it, whatever CA says.
        return Sgf_encoding(UTF8, UTF8, False, False, bb)

    ascii_only = all(byte < 0x80 for byte in bytearray(bb))

    declared = _declared_charset(bb)
    declared_codec = None
    if declared is not None:
        try:
            declared_codec = sgf_properties.normalise_charset_name(declared)
        except LookupError:
            # The CA property names something Python doesn't know. That's a
            # broken file, but it shouldn't stop us working out what the bytes
            # really are.
            declared_codec = None

    try:
        game = sgf.Sgf_game.from_bytes(bb)
    except (ValueError, LookupError):
        # Most likely an unusable CA property. Parse again without believing
        # it, so that the data can still be examined.
        game = None

    if game is None:
        try:
            game = sgf.Sgf_game.from_bytes(bb, override_encoding="ISO-8859-1")
        except (ValueError, LookupError) as e:
            raise SgfEncodingError(str(e)) from None
    elif not game.get_root().has_property("CA"):
        declared = None
        declared_codec = None

    if ascii_only and game.get_root().has_property("CA"):
        # Every ASCII-compatible encoding decodes these bytes the same way,
        # so there is nothing to detect and nothing to convert.
        normalised = declared_codec or declared
        return Sgf_encoding(normalised, normalised, False, True, bb)

    # When the file declares a usable encoding, try that first: a file that
    # says what it is should be believed. When it declares nothing there is no
    # evidence to prefer except guesswork, so try UTF-8 before ISO-8859-1
    # (which can decode any byte sequence, and so always succeeds).
    if declared_codec is None:
        order = (UTF8, "ISO-8859-1")
    else:
        order = (declared_codec, UTF8, "ISO-8859-1")

    candidates = []
    for candidate in order:
        if candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        ok, _ = _check_encoding(bb, candidate)
        if ok:
            return Sgf_encoding(candidate, declared, declared != candidate,
                                ascii_only, bb)

    raise SgfEncodingError(
        "can't determine the encoding of the SGF data (tried %s)"
        % ", ".join(candidates))


def detect_game(game):
    """Report the character encoding an Sgf_game's data claims to use.

    game -- Sgf_game

    Returns an Sgf_encoding, whose encoding is taken from the game's CA
    property (or the specification's default of ISO-8859-1).

    Unlike detect_bytes(), this cannot notice a file whose CA property
    disagrees with its contents, because the original bytes (and so the
    distinction between the declared and actual encodings) are not available
    from an Sgf_game.

    """
    try:
        encoding = game.get_charset()
    except (KeyError, LookupError, ValueError):
        encoding = "ISO-8859-1"
    return Sgf_encoding(encoding, encoding, False, False, game.serialise())


def convert_game_to_utf8(game, encoding=None):
    """Serialise an SGF game as UTF-8.

    game     -- Sgf_game
    encoding -- the encoding to read the game's text values as (optional)

    Returns a bytes object containing UTF-8 SGF data, with its CA property set
    to "UTF-8".

    If 'encoding' isn't specified, the game's own raw property encoding is
    used. Pass a detected encoding (from detect_bytes()) to convert a file
    that declares the wrong one.

    Raises UnicodeDecodeError if a text value can't be decoded using
    'encoding', and UnicodeEncodeError if it can't be represented in UTF-8.

    """
    if encoding is not None:
        game = _game_from_bytes(game.serialise(), encoding)
    root = game.get_root()
    # Re-encode every text value, so that the raw values are UTF-8 rather than
    # whatever encoding the file used.
    for node in _walk_nodes(root):
        for identifier in sorted(node.get_raw_property_map()):
            if identifier in _text_identifiers and identifier != "CA":
                node.set(identifier, node.get(identifier))
    root.set("CA", UTF8)
    return game.serialise()
