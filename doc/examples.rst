Examples
========

Reading from a file
-------------------

::

  from sgfmill import sgf
  with open("foo.sgf", "rb") as f:
      game = sgf.Sgf_game.from_bytes(f.read())
  winner = game.get_winner()
  board_size = game.get_size()
  root_node = game.get_root()
  b_player = root_node.get("PB")
  w_player = root_node.get("PW")
  for node in game.get_main_sequence():
      print(node.get_move())


Recording a game
----------------

::

  from sgfmill import sgf
  game = sgf.Sgf_game(size=13)
  for move_info in ...:
      node = game.extend_main_sequence()
      node.set_move(move_info.colour, move_info.move)
      if move_info.comment is not None:
          node.set("C", move_info.comment)
  with open(pathname, "wb") as f:
      f.write(game.serialise())


Modifying a game
----------------

::

  >>> from sgfmill import sgf
  >>> game = sgf.Sgf_game.from_string("(;FF[4]GM[1]SZ[9];B[ee];W[ge])")
  >>> root_node = game.get_root()
  >>> root_node.set("RE", "B+R")
  >>> new_node = game.extend_main_sequence()
  >>> new_node.set_move("b", (2, 3))
  >>> [node.get_move() for node in game.get_main_sequence()]
  [(None, None), ('b', (4, 4)), ('w', (4, 6)), ('b', (2, 3))]
  >>> game.serialise()
  b'(;FF[4]CA[UTF-8]GM[1]RE[B+R]SZ[9];B[ee];W[ge];B[dg])\n'


See also the :script:`show_sgf.py`, :script:`split_sgf_collection.py`,
:script:`report_sgf_properties.py`, :script:`transform_sgf.py` and
:script:`convert_sgf_encoding.py` example scripts.


The example scripts
-------------------

The following example scripts are available in the :file:`examples/` directory
of the Sgfmill source distribution.

They may be independently useful, as well as illustrating the library API.

See the top of each script for further information.

See :ref:`running the example scripts <running the example scripts>` for notes
on making the :mod:`!sgfmill` package available for use with the example
scripts.


.. script:: show_sgf.py

  Prints an ASCII diagram of the position from an |sgf| file.

  This demonstrates the :mod:`~sgfmill.sgf`, :mod:`~sgfmill.sgf_moves`, and
  :mod:`~sgfmill.ascii_boards` modules.


.. script:: split_sgf_collection.py

  Splits a file containing an |sgf| game collection into multiple files.

  This demonstrates the parsing functions from the :mod:`!sgf_grammar` module.


.. script:: report_sgf_properties.py

  Reports properties in an |sgf| file which aren't defined by FF[4], and can
  remove them to produce a file that only uses standard properties.

  This demonstrates the :mod:`~sgfmill.sgf_normalise` module.


.. script:: transform_sgf.py

  Flips or turns the board of an |sgf| file, saving the result to a new file.

  This demonstrates the :mod:`~sgfmill.sgf_transform` module.


.. script:: convert_sgf_encoding.py

  Reports the character encoding used by an |sgf| file, and can rewrite it in
  UTF-8.

  This demonstrates the :mod:`~sgfmill.sgf_encoding` module.


The SGF Toolkit application
---------------------------

The :file:`App/` directory holds **SGF Toolkit**, a small `Textual
<https://textual.textualize.io>`_ application that puts the functions described
here behind a keyboard-driven interface: a list of operations, a tabbed area of
results (including an ASCII board diagram), and a file explorer for choosing the
file to work on.

Unlike the example scripts, it requires a third-party package (``textual``).
The :mod:`!sgfmill` library itself has no dependencies.

::

    pip install textual
    python run_sgf_toolkit.py [directory]

See :file:`App/README.md` for the layout, the key bindings, and which library
call each operation uses.


