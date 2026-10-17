"""Geometric transformations of an SGF game's board.

Provides the four transformations a board editor normally offers: flipping the
board vertically or horizontally, and turning it a quarter-turn clockwise or
anti-clockwise.

Every property that refers to points on the board is transformed, including
markup, territory, and the points in labels, arrows and lines. Properties which
don't refer to board points (comments, player names, and so on) are unaffected.

::

    >>> from sgfmill import sgf, sgf_transform
    >>> game = sgf.Sgf_game.from_bytes(open("game.sgf", "rb").read())
    >>> turned = sgf_transform.transform_game(game, sgf_transform.ROTATE_CW)

Coordinate system
  Sgfmill represents a point as a pair (row, column), with (0, 0) at the bottom
  left (the GTP convention). These transformations are defined in those terms,
  so that they match what a viewer showing the board in the usual orientation
  will display:

  ================ =========================================
  Transformation   Effect on (row, col)
  ================ =========================================
  FLIP_VERTICAL    (size-1-row, col)
  FLIP_HORIZONTAL  (row, size-1-col)
  ROTATE_CW        (size-1-col, row)
  ROTATE_ACW       (col, size-1-row)
  ================ =========================================

  Which way a rotation goes is fixed by FF[4], which says that a point on the
  first row of the board moves to the last column when the board is turned 90
  degrees clockwise ('a' becomes 'i' on a 19x19 board). Read in the display
  orientation, that takes the top-left corner to the top-right.

  "Vertical flip" is taken to mean turning the board over about a vertical
  axis, ie swapping the left and right sides (which is the same as a
  horizontal mirror). If you want the top and bottom exchanged, that is
  :data:`FLIP_HORIZONTAL`.

  All four transformations are exact inverses or repeats of one another:
  applying :data:`ROTATE_CW` four times, or either flip twice, returns the
  board to its original position.

Arrows and lines
  The two points of an ``AR`` or ``LN`` value are transformed independently, so
  an arrow keeps pointing the same way relative to the board. Because an arrow
  is directional, the order of its two points is preserved.

Board size
  These transformations are defined for square boards, which is all that this
  library supports.

"""

__all__ = ["FLIP_VERTICAL", "FLIP_HORIZONTAL", "ROTATE_CW", "ROTATE_ACW",
           "TRANSFORMATIONS", "transform_point", "transform_game"]


def _flip_vertical(row, col, side):
    return side-1-row, col

def _flip_horizontal(row, col, side):
    return row, side-1-col

def _rotate_cw(row, col, side):
    return side-1-col, row

def _rotate_acw(row, col, side):
    return col, side-1-row


#: Flip the board about a vertical axis, swapping left and right.
FLIP_VERTICAL = "flip_vertical"

#: Flip the board about a horizontal axis, swapping top and bottom.
FLIP_HORIZONTAL = "flip_horizontal"

#: Turn the board a quarter-turn clockwise.
ROTATE_CW = "rotate_cw"

#: Turn the board a quarter-turn anti-clockwise.
ROTATE_ACW = "rotate_acw"

#: The available transformations, as a tuple.
TRANSFORMATIONS = (FLIP_VERTICAL, FLIP_HORIZONTAL, ROTATE_CW, ROTATE_ACW)

_functions = {
    FLIP_VERTICAL:   _flip_vertical,
    FLIP_HORIZONTAL: _flip_horizontal,
    ROTATE_CW:       _rotate_cw,
    ROTATE_ACW:      _rotate_acw,
}


# Properties whose value is a single point (a move).
_point_properties = frozenset(["B", "W"])

# Properties whose value is a list of points or stones (a set, when read).
_point_list_properties = frozenset(
    ["AB", "AW", "AE", "CR", "MA", "SL", "SQ", "TR", "TB", "TW"])

# Properties whose value is a list of points which may be empty (an elist).
_point_elist_properties = frozenset(["DD", "VW"])

# Properties whose value is a list of pairs of points.
_point_pair_list_properties = frozenset(["AR", "LN"])


def transform_point(point, transformation, side):
    """Apply a transformation to a single point.

    point          -- pair (row, col), or None (for a pass)
    transformation -- one of the TRANSFORMATIONS constants
    side           -- board size (int)

    Returns a pair (row, col), or None.

    Raises ValueError if the transformation isn't recognised.

    A pass (None) is returned unchanged, as it has no position.

    """
    try:
        fn = _functions[transformation]
    except KeyError:
        raise ValueError("unknown transformation: %s" % (transformation,)) from None
    if point is None:
        return None
    row, col = point
    return fn(row, col, side)


def _transform_node(node, transformation, side):
    """Transform the point-bearing properties of a single node.

    The new values are all worked out before any of them are stored, so that a
    malformed value leaves the node untouched.

    """
    ident_map = node.get_raw_property_map()
    changes = []

    for identifier in _point_properties:
        if identifier in ident_map:
            changes.append((identifier,
                            transform_point(node.get(identifier),
                                            transformation, side)))

    for identifier in _point_list_properties | _point_elist_properties:
        if identifier in ident_map:
            points = node.get(identifier)
            changes.append((identifier,
                            sorted(transform_point(p, transformation, side)
                                   for p in points)))

    for identifier in _point_pair_list_properties:
        if identifier in ident_map:
            pairs = node.get(identifier)
            changes.append(
                (identifier,
                 [tuple(transform_point(p, transformation, side) for p in pair)
                  for pair in pairs]))

    if "LB" in ident_map:
        changes.append(
            ("LB", [(transform_point(p, transformation, side), text)
                    for p, text in node.get("LB")]))

    for identifier, value in changes:
        node.set(identifier, value)


def transform_game(game, transformation):
    """Apply a transformation to every board reference in an SGF game.

    game           -- Sgf_game (modified in place)
    transformation -- one of the TRANSFORMATIONS constants

    The whole tree is transformed, including variations. The game's tree
    structure, and properties which don't refer to board points, are unchanged.

    Raises ValueError if the transformation isn't recognised.

    To transform a game without modifying the original, transform a copy::

        copy = sgf.Sgf_game.from_bytes(game.serialise())
        sgf_transform.transform_game(copy, sgf_transform.ROTATE_CW)

    """
    if transformation not in TRANSFORMATIONS:
        raise ValueError("unknown transformation: %s" % (transformation,))
    side = game.get_size()
    for node in _walk_nodes(game.get_root()):
        _transform_node(node, transformation, side)


def _walk_nodes(node):
    """Yield 'node' and all its descendants, in tree order (depth first)."""
    yield node
    for child in node:
        yield from _walk_nodes(child)
