"""Reports non-standard properties in an SGF game, and can remove them.

The SGF specification allows an application to add its own properties; their
identifiers conventionally begin with an upper-case letter (see the "Private"
and "Unknown properties" sections of the FF[4] specification). Such properties
are useful to the program that wrote them, but other software must ignore them,
and a file containing them is not portable.

This module finds properties that aren't defined by FF[4] (for Go), so that an
application can report them to the user, or strip them to produce a file that
only uses standard properties.

Standard properties
  The set of identifiers treated as standard is :data:`STANDARD_PROPERTIES`:
  the "general" FF[4] properties, together with the Go-specific properties
  ``HA``, ``KM``, ``TB`` and ``TW``.

  Note that this includes the three FF[4] properties which Sgfmill has no
  interpretation for: ``ID``, ``L`` and ``LT``. They are standard, so they are
  not reported; but this library can only access them as raw values.

  Pass a different set as the ``standard`` argument to test for properties
  specific to some other game (``GM``), or to treat some private properties as
  acceptable.

Checking a game
  ::

    >>> from sgfmill import sgf, sgf_normalise
    >>> game = sgf.Sgf_game.from_bytes(open("game.sgf", "rb").read())
    >>> report = sgf_normalise.check_game(game)
    >>> print(report)
    Non-standard properties: LV, MULTIGOGM
    >>> for name, nodes in sorted(report.findings().items()):
    ...     print("%s appears in %d node(s)" % (name, len(nodes)))

Removing them
  ::

    >>> report = sgf_normalise.clean_game(game)
    >>> print(report)
    Removed non-standard properties: LV, MULTIGOGM
    >>> data = game.serialise()

  :func:`clean_game` modifies the game in place; it does not change the tree
  structure, and it never removes a standard property, so a game that was
  valid FF[4] apart from its private properties remains valid.

This module works on the whole tree, including variations.
"""

__all__ = [
    "STANDARD_PROPERTIES",
    "MINIMUM_STANDARD_PROPERTIES",
    "Game_report",
    "check_game",
    "clean_game",
]


# The general properties defined by FF[4], plus the Go-specific ones.
#
# This is the "General properties" and "Go (GM[1]) specific properties" lists
# from the FF[4] specification, at
# http://www.red-bean.com/sgf/properties.html and
# http://www.red-bean.com/sgf/go.html
STANDARD_PROPERTIES = frozenset([
    # Move properties
    "B", "KO", "MN", "W",
    # Setup properties
    "AB", "AE", "AW", "PL",
    # Node annotation properties
    "C", "DM", "GB", "GW", "HO", "N", "UC", "V",
    # Move annotation properties
    "BM", "DO", "IT", "TE",
    # Markup properties
    "AR", "CR", "DD", "LB", "LN", "MA", "SL", "SQ", "TR",
    # Root properties
    "AP", "CA", "FF", "GM", "ST", "SZ",
    # Game info properties
    "AN", "BR", "BT", "CP", "DT", "EV", "GC", "GN", "ON", "OT", "PB", "PC",
    "PW", "RE", "RO", "RU", "SO", "TM", "US", "WR", "WT",
    # Timing properties
    "BL", "OB", "OW", "WL",
    # Miscellaneous properties
    "FG", "PM", "VW",
    # Game-info properties that FF[4] defines but deprecates (the "obsolete"
    # list in the specification). They are still standard properties.
    "ID", "L", "LT",
    # Go (GM[1]) specific properties
    "HA", "KM", "TB", "TW",
])

# The properties which FF[4] requires to be present in the root node of a game
# tree (FF, GM and SZ). Useful for a quick sanity check on a file.
MINIMUM_STANDARD_PROPERTIES = frozenset(["FF", "GM", "SZ"])


def _walk_nodes(node):
    """Yield 'node' and all its descendants, in tree order (depth first)."""
    yield node
    for child in node:
        yield from _walk_nodes(child)


class Game_report:
    """A summary of the non-standard properties found in (or removed from) a game.

    Public attributes (treat as read-only):
      findings -- dict mapping property identifier to list of Tree_node
      removed  -- bool: whether the properties were removed from the game

    The lists of nodes are in the order the nodes were visited, which is the
    order they appear in the tree (see find_nodes()).

    """
    def __init__(self, findings, removed):
        self.findings = findings
        self.removed = removed

    def properties(self):
        """Return the identifiers of the properties found, sorted.

        Returns a list of strings.

        """
        return sorted(self.findings)

    def nodes(self):
        """Return the nodes containing at least one non-standard property.

        Returns a list of Tree_node objects, in tree order, without duplicates.

        """
        result = []
        seen = set()
        for name in self.properties():
            for node in self.findings[name]:
                if id(node) not in seen:
                    seen.add(id(node))
                    result.append(node)
        return result

    def __bool__(self):
        """Return whether any non-standard property was found."""
        return bool(self.findings)

    def __len__(self):
        """Return the number of distinct non-standard properties found."""
        return len(self.findings)

    def __str__(self):
        if not self.findings:
            return "No non-standard properties found"
        names = ", ".join(self.properties())
        if self.removed:
            return "Removed non-standard properties: %s" % names
        return "Non-standard properties: %s" % names


def check_game(game, standard=STANDARD_PROPERTIES):
    """Find the non-standard properties in an SGF game.

    game     -- Sgf_game
    standard -- set of property identifiers to treat as standard
                (default STANDARD_PROPERTIES)

    Returns a Game_report. The game is not modified.

    """
    findings = {}
    for node in _walk_nodes(game.get_root()):
        for identifier in sorted(node.get_raw_property_map()):
            if identifier not in standard:
                findings.setdefault(identifier, []).append(node)
    return Game_report(findings, removed=False)


def clean_game(game, standard=STANDARD_PROPERTIES):
    """Remove the non-standard properties from an SGF game.

    game     -- Sgf_game (modified in place)
    standard -- set of property identifiers to treat as standard
                (default STANDARD_PROPERTIES)

    Returns a Game_report describing what was removed.

    The game's tree structure is not changed. Only properties whose identifiers
    aren't in 'standard' are removed.

    """
    findings = {}
    for node in _walk_nodes(game.get_root()):
        # Iterate over a snapshot of the identifiers: unset() modifies the map.
        for identifier in sorted(node.get_raw_property_map()):
            if identifier not in standard:
                findings.setdefault(identifier, []).append(node)
                node.unset(identifier)
    return Game_report(findings, removed=True)
