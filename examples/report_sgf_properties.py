"""Report (and optionally remove) non-standard properties in an SGF file.

This demonstrates the sgf_normalise module.

"""

import sys
from optparse import OptionParser

from sgfmill import sgf
from sgfmill import sgf_normalise

def report_sgf_file(pathname, clean, outpathname):
    with open(pathname, "rb") as f:
        sgf_src = f.read()
    try:
        sgf_game = sgf.Sgf_game.from_bytes(sgf_src)
    except ValueError:
        raise Exception("bad sgf file")

    if clean:
        report = sgf_normalise.clean_game(sgf_game)
    else:
        report = sgf_normalise.check_game(sgf_game)

    if not report:
        print("%s: no non-standard properties" % pathname)
        return 0

    print("%s:" % pathname)
    for name in report.properties():
        nodes = report.findings[name]
        print("  %-12s in %d node%s" % (name, len(nodes),
                                        "" if len(nodes) == 1 else "s"))

    if clean:
        if outpathname is None:
            outpathname = pathname
        with open(outpathname, "wb") as f:
            f.write(sgf_game.serialise())
        print("wrote %s" % outpathname)
    return len(report)

_description = """\
Report properties in an SGF file which aren't defined by FF[4] (for Go).

With --clean, the non-standard properties are removed and the result is written
to the output file (or back to the input file).
"""

def main(argv):
    parser = OptionParser(usage="%prog [options] <filename>",
                          description=_description)
    parser.add_option("-c", "--clean", action="store_true", default=False,
                      help="remove the non-standard properties")
    parser.add_option("-o", "--output", metavar="FILE", default=None,
                      help="where to write the cleaned file (implies --clean)")
    opts, args = parser.parse_args(argv)
    if not args:
        parser.error("not enough arguments")
    if len(args) > 1:
        parser.error("too many arguments")
    clean = opts.clean or opts.output is not None
    if not clean and opts.output is not None:
        parser.error("--output requires --clean")
    try:
        report_sgf_file(args[0], clean, opts.output)
    except Exception as e:
        print("report_sgf_properties:", str(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1:])
