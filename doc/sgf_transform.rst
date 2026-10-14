The :mod:`!sgf_transform` module
--------------------------------

.. module:: sgfmill.sgf_transform
   :synopsis: Flipping and turning an SGF game's board.

The :mod:`!sgfmill.sgf_transform` module applies the four board transformations
a Go editor normally offers: flipping the board vertically or horizontally, and
turning it a quarter-turn clockwise or anti-clockwise.

Every property which refers to points on the board is transformed, including
moves, stones, markup, and the points in labels, arrows and lines. Properties
which don't refer to board points (comments, player names, and so on) are left
alone. The whole tree is transformed, including variations.

::

   >>> from sgfmill import sgf, sgf_transform
   >>> game = sgf.Sgf_game.from_bytes(open("game.sgf", "rb").read())
   >>> sgf_transform.transform_game(game, sgf_transform.ROTATE_CW)
   >>> open("turned.sgf", "wb").write(game.serialise())

A game is transformed in place. To keep the original, transform a copy::

   >>> copy = sgf.Sgf_game.from_bytes(game.serialise())
   >>> sgf_transform.transform_game(copy, sgf_transform.FLIP_HORIZONTAL)

See also the :script:`transform_sgf.py` example script.

Coordinates
...........

Sgfmill represents a point as a pair (*row*, *col*), with ``(0, 0)`` at the
bottom left (see :doc:`property_types`). The transformations are defined in
those terms:

====================================== ==========================
Transformation                         ``(row, col)`` becomes
====================================== ==========================
:data:`FLIP_VERTICAL`                  ``(side-1-row, col)``
:data:`FLIP_HORIZONTAL`                ``(row, side-1-col)``
:data:`ROTATE_CW`                      ``(col, side-1-row)``
:data:`ROTATE_ACW`                     ``(side-1-col, row)``
====================================== ==========================

"Vertical flip" means turning the board over about a vertical axis, which
swaps the left and right sides of the board (it is the same as a horizontal
mirror). If you want the top and bottom exchanged, that is
:data:`FLIP_HORIZONTAL`.

Each transformation is an exact inverse or repeat of another: applying
:data:`ROTATE_CW` four times, or either flip twice, returns the board to its
original position. A clockwise turn is undone by an anti-clockwise one.

Because an arrow points from its first point to its second, the order of an
``AR`` value's two points is preserved.


.. data:: FLIP_VERTICAL

   Identifier for a flip about a vertical axis, swapping left and right.


.. data:: FLIP_HORIZONTAL

   Identifier for a flip about a horizontal axis, swapping top and bottom.


.. data:: ROTATE_CW

   Identifier for a quarter-turn clockwise.


.. data:: ROTATE_ACW

   Identifier for a quarter-turn anti-clockwise.


.. data:: TRANSFORMATIONS

   A tuple of the four identifiers above.


.. function:: transform_point(point, transformation, side)

   :rtype: pair (*row*, *col*), or ``None``

   Returns *point* (a pair (*row*, *col*), or ``None`` for a pass) with
   *transformation* applied, on a board of size *side*.

   A pass (``None``) is returned unchanged, as it has no position.

   Raises :exc:`ValueError` if *transformation* isn't recognised.


.. function:: transform_game(game, transformation)

   Applies *transformation* to every board reference in *game* (an
   :class:`.Sgf_game`), modifying it in place.

   Raises :exc:`ValueError` if *transformation* isn't recognised. In that case
   *game* is not modified.
