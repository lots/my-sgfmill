"""Flip or turn the board of an SGF file, saving the result.

This demonstrates the sgf_transform module.

"""

import sys
from optparse import OptionParser

from sgfmill import sgf
from sgfmill import sgf_transform

_transformations = {
    "vflip": sgf_transform.FLIP_VERTICAL,
    "hflip": sgf_transform.FLIP_HORIZONTAL,
    "cw": sgf_transform.ROTATE_CW,
    "acw": sgf_transform.ROTATE_ACW,
    }

def transform_sgf_file(pathname, transformation, outpathname):
    with open(pathname, "rb") as f:
        sgf_src = f.read()
    try:
        sgf_game = sgf.Sgf_game.from_bytes(sgf_src)
    except ValueError:
        raise Exception("bad sgf file")
    sgf_transform.transform_game(sgf_game, transformation)
    with open(outpathname, "wb") as f:
        f.write(sgf_game.serialise())

_description = """\
Flip or turn the board of an SGF file.

TRANSFORM is one of:
  vflip   swap the left and right halves of the board
  hflip   swap the top and bottom halves of the board
  cw      turn the board 90 degrees clockwise
  acw     turn the board 90 degrees anticlockwise

Every move, stone and markup is transformed; comments and other properties are
left alone.
"""

def main(argv):
    parser = OptionParser(usage="%prog <transform> <filename> <outfile>",
                          description=_description)
    opts, args = parser.parse_args(argv)
    if len(args) < 3:
        parser.error("not enough arguments")
    if len(args) > 3:
        parser.error("too many arguments")
    name, pathname, outpathname = args
    try:
        transformation = _transformations[name]
    except KeyError:
        parser.error("unknown transform: %s (expected one of %s)"
                     % (name, ", ".join(sorted(_transformations))))
    try:
        transform_sgf_file(pathname, transformation, outpathname)
    except Exception as e:
        print("transform_sgf:", str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1:])
