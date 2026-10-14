The :mod:`!sgf_normalise` module
---------------------------------

.. module:: sgfmill.sgf_normalise
   :synopsis: Reporting and removing non-standard SGF properties.

The :mod:`!sgfmill.sgf_normalise` module finds properties in an |sgf| game
which aren't defined by FF[4], and can remove them.

|SGF| allows an application to add properties of its own; their identifiers
conventionally begin with an upper-case letter. They are useful to the program
that wrote them, but other software has to ignore them, and a file containing
them is not portable. This module is for reporting them to a user, or for
producing a file that only uses standard properties.

The properties treated as standard are the "general" FF[4] properties together
with the Go-specific ones (``HA``, ``KM``, ``TB`` and ``TW``). Note that this
includes ``ID``, ``L`` and ``LT``, which FF[4] defines (though it deprecates
them) but which this library has no interpretation for.

The whole tree is examined, including variations. Neither function changes the
tree structure, so a game that was valid FF[4] apart from its private
properties remains valid.

::

   >>> from sgfmill import sgf, sgf_normalise
   >>> game = sgf.Sgf_game.from_bytes(open("game.sgf", "rb").read())
   >>> report = sgf_normalise.check_game(game)
   >>> print(report)
   Non-standard properties: LV, MULTIGOGM
   >>> for name in report.properties():
   ...     print("%s: %d node(s)" % (name, len(report.findings[name])))
   LV: 1 node(s)
   MULTIGOGM: 1 node(s)

   >>> report = sgf_normalise.clean_game(game)
   >>> print(report)
   Removed non-standard properties: LV, MULTIGOGM
   >>> open("clean.sgf", "wb").write(game.serialise())

See also the :script:`report_sgf_properties.py` example script.


.. data:: STANDARD_PROPERTIES

   A :class:`frozenset` of the property identifiers which are treated as
   standard: the general FF[4] properties, plus the Go-specific ones
   (``HA``, ``KM``, ``TB``, ``TW``).


.. data:: MINIMUM_STANDARD_PROPERTIES

   A :class:`frozenset` of the properties which FF[4] requires to be present in
   the root node of a game tree: ``FF``, ``GM`` and ``SZ``.


.. class:: Game_report

   A summary of the non-standard properties found in (or removed from) a game.
   Returned by :func:`check_game` and :func:`clean_game`.

   It is false (in the boolean sense) if no non-standard property was found,
   and its length is the number of distinct properties found.

   .. attribute:: findings

      A :class:`dict` mapping property identifier to the list of
      :class:`.Tree_node` objects which contain it, in tree order.

      Treat this as read-only.

   .. attribute:: removed

      :const:`True` if the properties were removed from the game, otherwise
      :const:`False`.

   .. method:: properties()

      Returns the identifiers of the properties found, as a sorted list of
      strings.

   .. method:: nodes()

      Returns the nodes containing at least one non-standard property, as a
      list of :class:`.Tree_node` objects in tree order, without duplicates.


.. function:: check_game(game[, standard])

   :rtype: :class:`.Game_report`

   Returns a report on the non-standard properties in *game* (an
   :class:`.Sgf_game`), without modifying it.

   *standard* (optional) is the set of property identifiers to treat as
   standard; the default is :data:`STANDARD_PROPERTIES`. Pass a different set
   to check for properties specific to some other game (``GM``), or to accept
   some private properties.


.. function:: clean_game(game[, standard])

   :rtype: :class:`.Game_report`

   Removes the non-standard properties from *game* (an :class:`.Sgf_game`),
   modifying it in place, and returns a report describing what was removed.

   *standard* (optional) is as for :func:`check_game`.

   The game's tree structure is not changed. Only properties whose identifiers
   aren't in *standard* are removed, so standard properties (including a
   comment, or a handicap) always survive.
