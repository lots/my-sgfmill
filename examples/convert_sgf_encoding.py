"""Report the character encoding of an SGF file, and convert it to UTF-8.

This demonstrates the sgf_encoding module.

"""

import sys
from optparse import OptionParser

from sgfmill import sgf
from sgfmill import sgf_encoding

def convert_sgf_file(pathname, outpathname, force_encoding):
    with open(pathname, "rb") as f:
        sgf_src = f.read()
    try:
        result = sgf_encoding.detect_bytes(sgf_src)
    except sgf_encoding.SgfEncodingError as e:
        raise Exception(str(e))

    if force_encoding is not None:
        print("%s: using %s (as requested)" % (pathname, force_encoding))
    else:
        print("%s: %s" % (pathname, result))
        if result.mismatch and not result.ascii_only:
            print("  (the file's CA property disagrees with its contents)")

    if outpathname is None:
        if result.needs_conversion():
            print("  convert with -o FILE to write UTF-8")
        return

    if force_encoding is not None:
        try:
            sgf_game = sgf.Sgf_game.from_bytes(sgf_src,
                                               override_encoding=force_encoding)
        except (ValueError, LookupError) as e:
            raise Exception(str(e)) from None
    else:
        sgf_game = result.game()
    data = sgf_encoding.convert_game_to_utf8(sgf_game)
    with open(outpathname, "wb") as f:
        f.write(data)
    print("wrote %s (UTF-8)" % outpathname)

_description = """\
Report the character encoding used by an SGF file.

With -o, the file is rewritten in UTF-8. The encoding is worked out from the CA
property and the file's contents; use -e to override the guess.
"""

def main(argv):
    parser = OptionParser(usage="%prog [options] <filename>",
                          description=_description)
    parser.add_option("-o", "--output", metavar="FILE", default=None,
                      help="write a UTF-8 copy to FILE")
    parser.add_option("-e", "--encoding", metavar="NAME", default=None,
                      help="treat the file as being in this encoding")
    opts, args = parser.parse_args(argv)
    if not args:
        parser.error("not enough arguments")
    if len(args) > 1:
        parser.error("too many arguments")
    try:
        convert_sgf_file(args[0], opts.output, opts.encoding)
    except Exception as e:
        print("convert_sgf_encoding:", str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1:])
