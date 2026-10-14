Changes
=======

* Added SGF Toolkit, a Textual application in the :file:`App/` directory which
  puts the library's functions behind a keyboard-driven interface with a
  VS Code style file explorer. It is an optional companion: the library itself
  still has no dependencies.

  :file:`App/run_sgf_toolkit.py` adds the repository root to ``sys.path``
  itself, so it can be run from any directory rather than only from the
  repository root. Two environment variables (``SGF_TOOLKIT_HEADLESS`` and
  ``SGF_TOOLKIT_EXIT_AFTER_STARTUP``) let it start where there is no terminal.

  The window is arranged in the order you work in -- select a target (the file
  explorer, on the left), choose an action, then read the result -- with a help
  pane across the bottom describing the highlighted action.

* Added the :mod:`~sgfmill.sgf_normalise` module, which reports the
  non-standard properties in an |sgf| game and can remove them to produce a
  file that only uses standard properties.

* Added the :mod:`~sgfmill.sgf_transform` module, which flips or turns the
  board of an |sgf| game: vertical flip, horizontal flip, and quarter-turns
  clockwise and anti-clockwise.

* Added the :mod:`~sgfmill.sgf_encoding` module, which works out the character
  encoding of |sgf| data and converts it to UTF-8.

* Added the :script:`report_sgf_properties.py`, :script:`transform_sgf.py` and
  :script:`convert_sgf_encoding.py` example scripts.

* A pass is now written as the FF[4] empty value (``B[]``) rather than as
  ``tt``, on boards of every size. The older ``tt`` encoding is still accepted
  when reading a board of 19x19 or smaller.

* Bug fix: ``test_installed_sgfmill`` no longer imports the sibling ``sgfmill``
  directory instead of the installed package when it is invoked by an absolute
  path. It also no longer uses the ``imp`` module, which was removed in Python
  3.12.

* Sped up the :class:`.Board` implementation (thanks to Lin, Yong Xiang).

* The minimum Python version is now 3.5.


Sgfmill 1.1.1 (2018-05-20)
--------------------------

* Sped up the :class:`.Board` implementation (thanks to Seth Troisi).


Sgfmill 1.1 (2018-02-11)
------------------------

* The parser now permits lower-case letters in *PropIdents*; see
  :doc:`parsing` for details.

* Bug fix: :meth:`.Tree_node.set` didn't check its ``identifier`` parameter
  was a well-formed *PropIdent*.

* Bug fix: :meth:`.Tree_node.set` was willing to store invalid values for
  properties of type Number, if fed invalid input.


Sgfmill 1.0 (2017-04-17)
------------------------

* Python 3 port of the SGF code from Gomill__ 0.8.

* Added the :mod:`.sgf_board_interface` module.

.. __: https://mjw.woodcraft.me.uk/gomill/

