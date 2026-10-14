The :mod:`!sgf_encoding` module
-------------------------------

.. module:: sgfmill.sgf_encoding
   :synopsis: Detecting an SGF file's encoding, and converting it to UTF-8.

The :mod:`!sgfmill.sgf_encoding` module works out the character encoding that
an |sgf| file's bytes are actually in, and can rewrite the data as UTF-8.

|SGF| says that Text and SimpleText property values use the encoding named by
the root ``CA`` property, defaulting to ``ISO-8859-1``. In practice files are
often written with an encoding other than the one they declare, or with no
``CA`` property at all, which makes their comments and player names display as
mojibake.

::

   >>> from sgfmill import sgf_encoding
   >>> result = sgf_encoding.detect_bytes(open("game.sgf", "rb").read())
   >>> print(result)
   UTF-8 (file declares ISO-8859-1)
   >>> if result.needs_conversion():
   ...     data = sgf_encoding.convert_game_to_utf8(result.game())
   ...     open("game-utf8.sgf", "wb").write(data)

See also the :script:`convert_sgf_encoding.py` example script.


How the encoding is worked out
..............................

#. A UTF-8 byte order mark settles it, regardless of the ``CA`` property.

#. Otherwise the ``CA`` property is read. If it names a Python codec, and every
   Text and SimpleText value can be decoded with it, that encoding is used: a
   file that says what it is, is believed.

#. Otherwise the bytes are tested against ``UTF-8``, which is the usual intent.
   UTF-8 is quite hard to satisfy by accident, so this is a reliable signal.

#. Otherwise ``ISO-8859-1`` is used, as it can decode any byte sequence at all.
   It therefore never fails, but it may well be wrong: with no better evidence
   there is no way to distinguish, for example, Latin-1 from CP1252.

Step 2 is skipped for files containing no non-ASCII bytes, because every
ASCII-compatible encoding decodes those identically. Such a file doesn't need
converting, and the declared encoding is reported.

What this cannot do is notice a file that declares an encoding which is wrong
but which still decodes its bytes. A UTF-8 file labelled ``CA[ISO-8859-1]`` is
ambiguous: those bytes form a valid Latin-1 string too, just not the intended
one. Detection therefore follows the declaration, and the disagreement is
reported (as :attr:`Sgf_encoding.mismatch`) rather than silently corrected.
Pass ``encoding="UTF-8"`` to :func:`convert_game_to_utf8` to override it.

Only properties which this library knows to be of Text or SimpleText type are
examined, and (when converting) re-encoded. Text in a private property isn't
detected, and its bytes are left as they are.

These functions work on a single game. For a collection, split it first (see
:mod:`!sgfmill.sgf_grammar`), or apply them to each game in turn.


.. data:: UTF8

   The encoding converted files are written in, ``"UTF-8"``.


.. exception:: SgfEncodingError

   Raised when an |sgf| file's encoding can't be determined, or when data can't
   be parsed using a requested encoding. It is a subclass of :exc:`Exception`.


.. class:: Sgf_encoding

   The result of examining an |sgf| file's character encoding. Returned by
   :func:`detect_bytes` and :func:`detect_game`.

   Its string form describes the detected encoding, and the ``CA`` property if
   that differs::

      >>> str(sgf_encoding.detect_bytes(data))
      'UTF-8 (file declares ISO-8859-1)'

   .. attribute:: encoding

      The encoding the data is in, as a name for a Python codec, in the
      normalised form used elsewhere in Sgfmill (eg ``"UTF-8"``).

   .. attribute:: declared

      The encoding named by the ``CA`` property, or ``None`` if the file has no
      ``CA`` property.

   .. attribute:: mismatch

      :const:`True` if :attr:`encoding` differs from :attr:`declared`.

   .. attribute:: ascii_only

      :const:`True` if the data contains no non-ASCII bytes.

   .. method:: needs_conversion()

      Returns whether the data would be changed by a conversion to UTF-8. This
      is true if :attr:`encoding` isn't already UTF-8.

   .. method:: game()

      :rtype: :class:`.Sgf_game`

      Returns an :class:`.Sgf_game` for the data, whose raw property encoding
      and ``CA`` property are the detected encoding.

      Raises :exc:`.SgfEncodingError` if the data can't be parsed, or if the
      detected encoding can't be used as a Python codec.


.. function:: detect_bytes(bb)

   :rtype: :class:`.Sgf_encoding`

   Works out the character encoding of some |sgf| data.

   *bb* is a bytes-like object, the contents of an |sgf| file. It may contain a
   collection; only the first game is examined.

   Raises :exc:`.SgfEncodingError` if the data can't be parsed at all. Note
   that a ``CA`` property naming an encoding that Python doesn't know is not an
   error here: the bytes are examined instead.


.. function:: detect_game(game)

   :rtype: :class:`.Sgf_encoding`

   Reports the encoding that *game* (an :class:`.Sgf_game`) claims to use, from
   its ``CA`` property (or the specification's default of ``ISO-8859-1``).

   Unlike :func:`detect_bytes`, this cannot notice a file whose ``CA`` property
   disagrees with its contents, because an :class:`.Sgf_game` doesn't keep the
   original bytes. Use :func:`detect_bytes` when you have them.


.. function:: convert_game_to_utf8(game[, encoding])

   :rtype: bytes

   Returns *game* (an :class:`.Sgf_game`) serialised as UTF-8, with its ``CA``
   property set to ``"UTF-8"``. Every Text and SimpleText value is re-encoded.

   *encoding* (optional) is the encoding to read the game's text values as. If
   it isn't given, the game's own raw property encoding is used. Pass the
   detected encoding (from :func:`detect_bytes`) to convert a file that
   declares the wrong one.

   Raises :exc:`UnicodeDecodeError` if a text value can't be decoded using
   *encoding*, and :exc:`UnicodeEncodeError` if it can't be represented in
   UTF-8.
