#!/usr/bin/env python3

#########################################################################
#
#   Copyright 2009 David Liang
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#   Revisions:
#   2009-04-22  File created
#   2009-08-24  Added -l option
#   2009-09-12  Changed string transformations to use native Python
#               Added option to use target filenames from stdin
#
#########################################################################

import sys, os, signal
import re, random
from os import path

__version__ = "0.7"
__doc__ = """
Rename files on the command line."""
__num__ = """
Number files on the command line in argument order. Safe reorderings are
allowed. For example `%(__prog__)s 2.jpg 1.jpg' swaps the two file names, and
`%(__prog__)s 1.jpg 1a.jpg 2.jpg' succeeds in renaming the last two files
(to "2.jpg" and "3.jpg" respectively) only if 3.jpg doesn't exist."""


def PrintError(*args, sep=': ', end='\n', file=sys.stderr):
    pargs = []
    for arg in args:
        if arg is not None and arg != '':
            pargs.append(arg)
    if pargs:
        print(*pargs, sep=sep, end=end, file=file)


class Exit(Exception):

    def __init__(self, status, *args):
        self.status = status
        self.args = args


def handler(signum, frame):
    msg = None

    if signum:
        for signame in ("SIGINT", "SIGQUIT", "SIGABRT"):
            if signum == getattr(signal, signame, None):
                msg="aborted"
        for signame in ("SIGHUP", "SIGTERM"):
            if signum == getattr(signal, signame, None):
                msg="terminated"

    if msg: raise Exit(signum, msg)


class StringTransform:

    from codecs import decode
    from collections import defaultdict

    _re_alnum = re.compile(r'[A-Za-z0-9]')
    _re_translit_range = re.compile(r'(.)-(.)', re.DOTALL)
    _re_char_run = re.compile(r'(.)\1+', re.DOTALL)

    class ParseError(Exception):
        def __init__(self, *args):
            self.args = args

    def __init__(self):
        self.clear()

    def clear(self):
        self.ops = []

    def addSubstitution(self, pat, sub, opts):
        invalid = re.search(r'[^aig\d]', opts)
        if invalid:
            raise self.ParseError( "invalid regular expression flag",
                                   invalid.group() )
        flags = 0
        count = 1
        if 'a' in opts: flags |= re.A
        if 'i' in opts: flags |= re.I
        if 'g' in opts:
            count = 0
        else:
            num = re.search(r'\d+', opts)
            if num:
                count = int(num.group())
        try:
            regex = re.compile(pat, flags)
        except re.error as e:
            raise self.ParseError(*e.args)

        if pat or sub:
            self.ops.append((regex, sub, count))


    @classmethod
    def ordinalsList(cls, str):
        list = []
        while str:
            run = cls._re_translit_range.match(str)
            if run:
                start, end = (ord(c) for c in run.group(1, 2))
                if start > end:
                    raise cls.ParseError(
                              "invalid range in transliteration operator",
                              run.group(0) )
                while start <= end:
                    list.append(start)
                    start += 1
                str = str[3:]
            else:
                list.append(ord(str[0]))
                str = str[1:]
        return list

    @staticmethod
    def complementList(ords, length):
        list = []
        ords = set(ords)
        i = 0
        while len(list) < length:
            if i not in ords:
                list.append(i)
            i += 1
        return list

    @classmethod
    def squash(cls, string):
        return cls._re_char_run.sub(r'\1', string)


    def addTransliteration(self, chars, repl, opts):
        invalid = re.search(r'[^cds]', opts)
        if invalid:
            raise self.ParseError( "invalid transliteration flag",
                                   invalid.group() )
        complm, delete, squash = 'c' in opts, 'd' in opts, 's' in opts
        try:
            chars = self.decode(chars.encode(), 'unicode_escape')
            repl  = self.decode(repl.encode(),  'unicode_escape')
        except UnicodeDecodeError as e:
            raise self.ParseError( "'%s' codec can't decode position %d-%d"
                                   % (e.encoding, e.start, e.end), e.reason )
        char_a = self.ordinalsList(chars)
        repl_a = self.ordinalsList(repl)
        if complm:
            char_a = self.complementList(char_a, len(repl_a))

        map = dict()
        if delete:
            default = ''
            if complm:
                map = self.defaultdict(lambda: default)
        elif repl_a:
            default = repl_a[-1]
            if complm:
                map = self.defaultdict(lambda: default)
        else:
            repl_a = char_a

        for i, c in enumerate(char_a):
            if c in map: continue
            try:
                map[c] = repl_a[i]
            except IndexError:
                map[c] = default

        if not complm:
            if not chars:
                return
            elif not squash:
                self.ops.append(map)
                return
        try:
            chars = chars.replace('[', r'\[').replace(']', r'\]')
            if complm:
                regex = re.compile( ('[^'+chars+']' if chars else '.') + '+',
                                    re.DOTALL )
            else:
                regex = re.compile('['+chars+']+')

        except re.error as e:
            raise self.ParseError(*e.args)

        if squash:
            sub = lambda m: self.squash(m.group().translate(map))
        else:
            sub = lambda m: m.group().translate(map)

        self.ops.append((regex, sub, 0))
        return


    def addOperations(self, expr_list):
        expr = expr_list
        while True:
            expr = expr.strip(' \t;')
            if not expr:
                return
            elif expr.startswith('s'):
                op = 's'
            elif expr.startswith('y') or expr.startswith('tr'):
                op = 'y'
            else:
                raise self.ParseError("unrecognized operation", expr)

            i = (2 if expr.startswith('tr') else 1)
            if not expr[i:]:
                raise self.ParseError("unterminated expression", expr)
            elif self._re_alnum.match(expr[i]):
                raise self.ParseError("invalid delimiter", expr)

            sep = (r'\\' if expr[i] == '\\' else expr[i])
            i += 1
            mat = re.match( r'((?:\\.|[^\\'+sep+'])*)[' + sep + ']'
                            r'((?:\\.|[^\\'+sep+'])*)[' + sep + ']([^\s;]*)',
                            expr[i:] )
            if not mat:
                raise self.ParseError("unterminated expression", expr)
            elif op == 's':
                self.addSubstitution(*mat.groups(''))
            elif op == 'y':
                self.addTransliteration(*mat.groups(''))

            expr = expr[mat.end()+i:]


    def transform(self, string):
        for op in self.ops:
            if type(op) == tuple:
                string = op[0].sub(op[1], string, op[2])
            else:
                string = string.translate(op)
        return string


def shortPath(path):
    return _re_home.sub('~', path)

def tempSuffix():
    return '.%s.%d.%s' % (__prog__, _pid, ''.join(random.sample(_letters, 4)))

class Rename:

    def __init__(self, arg, path, new_name, new_path):
        self.arg = arg
        self.path = path
        self.new_name = new_name
        self.new_path = new_path
        self.temp_path = None
        self.renamed = False

    def __repr__(self):
        return "`%s' -> `%s'" % (self.arg, self.new_path)

    def __eq__(self, other):
        return self.path == other.path

    def tempMove(self):
        if (self.path == self.new_path):
            return
        while True:
            self.temp_path = self.path + tempSuffix()
            if not path.lexists(self.temp_path):
                break
        try:
            os.rename(self.arg, self.temp_path)
        except OSError as e:
            self.temp_path = None
            PrintError(self.arg, e.strerror)
            updateStatus(1)

    def doRename(self):
        if not self.temp_path or not path.lexists(self.temp_path):
            return
        if path.lexists(self.new_path):
            if not _force:
                PrintError(self.arg + " not renamed",
                           shortPath(self.new_path) + " exists")
                self.tempRevert()
                return
        try:
            os.rename(self.temp_path, self.new_path)
            _renamed[self.new_path] = self
            self.renamed = True
        except OSError as e:
            PrintError(self.arg + " not renamed",
                       e.filename, e.strerror)
            self.tempRevert()

    def tempRevert(self):
        if self.renamed or not self.temp_path or not path.lexists(self.temp_path):
            return
        try:
            if path.lexists(self.path):
                if self.path not in _renamed or \
                   not _renamed[self.path].undoRename():
                    from errno import EEXIST
                    raise OSError(EEXIST, "original location exists")
            os.rename(self.temp_path, self.path)
            self.temp_path = None
        except OSError as e:
            PrintError("could not revert " + shortPath(self.temp_path),
                       e.filename, e.strerror)
            updateStatus(4)

    def undoRename(self):
        if not self.renamed or not path.lexists(self.new_path):
            return False
        if path.lexists(self.path):
            if self.path not in _renamed or not _renamed[self.path].undoRename():
                return False
        try:
            os.rename(self.new_path, self.path)
            PrintError(self.arg + " not renamed",
                       shortPath(self.new_path) + " exists")
            self.renamed = False
            return True
        except OSError as e:
            return False

    def print(self):
        if self.renamed:
            if _verbose:
                print(self.arg, self.new_name, sep=': ')
        elif _noact:
            try:
                os.stat(self.arg)
                if self.path != self.new_path:
                    print(self.arg, self.new_name, sep=': ')
            except OSError as e:
                PrintError(self.arg, e.strerror)
                updateStatus(1)


def nextRename(arg, abspath):
    dest = sys.stdin.readline()
    if not dest:
        PrintError(arg + " not renamed", "no input")
        updateStatus(1)
        return None

    dest = dest.rstrip('\n')
    if not dest:
        if _verbose:
            print("skipping " + arg, "empty line", sep=': ')
        return None
    else:
        dest = path.abspath(dest)
        return Rename(arg, abspath, path.basename(dest), dest)

def generateRenames(args):
    global _counter

    pargs = tuple(arg.rstrip(os.sep) for arg in args)
    if _zpad:
        argslen = tuple(bool(s) for s in pargs).count(True)
        maxlen = len(str(_counter + _increment * (argslen - 1)))
        pf_number = '%0' + str(maxlen) + 'd'
    else:
        pf_number = '%d'

    renames = []
    paths_seen = set()

    for i, arg in enumerate(pargs):
        if not arg:
            try:
                os.rename(args[i], '')
            except OSError as e:
                PrintError(args[i], e.strerror)
                updateStatus(1)
            continue

        abspath = path.abspath(arg)

        if _stdin:
            rn = nextRename(args[i], abspath)
            if rn:
                renames.append(rn)
            continue

        if abspath in paths_seen:
            continue
        else:
            paths_seen.add(abspath)

        dirname, name = path.split(abspath)
        if not _wname:
            name, ext = path.splitext(name)

        if _do_fmt_number:
            next_name = _re_fmt_number.sub(r'\g<pre>' + (pf_number % _counter),
                                           _format)
            _counter += _increment
        else:
            next_name = _format

        if _do_fmt_name:
            name = _transform.transform(name).replace('\\', r'\\')
            next_name = _re_fmt_name.sub(r'\g<pre>' + name, next_name)

        if not _wname:
            next_name += (ext.lower() if _lower else ext)

        renames.append(Rename(args[i], abspath, next_name, path.join(dirname, next_name)))

    return renames


def updateStatus(code):
    global _status, _num_errors
    if code == 0:
        _status = 0
        _num_errors = 0
    else:
        _status = max(_status, code)
        _num_errors += 1

def instantiateGlobals():
    global _pid
    global _letters
    global _renamed
    _pid = os.getpid()
    _letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    _renamed = {}

    global _fmt_number
    global _fmt_name
    global _re_fmt_number
    global _re_fmt_name
    global _re_home
    _fmt_number = '{N}'
    _fmt_name = '{}'
    not_escaped = r'(?P<pre>(?:^|(?<=[^\\]))(?:\\\\)*)'
    _re_fmt_number = re.compile(not_escaped + _fmt_number)
    _re_fmt_name = re.compile(not_escaped + _fmt_name)
    _re_home = re.compile(r'^' + path.expanduser('~'))

def parseOptions(argv):
    global __usage__
    global _force
    global _verbose
    global _noact
    global _stdin
    global _wname
    global _lower
    global _format
    global _do_fmt_name
    global _do_fmt_number
    global _transform
    global _counter
    global _increment
    global _zpad

    number = "num" in __prog__

    from optparse import OptionParser, OptionGroup, OptParseError
    class OptParser(OptionParser):
        def error(self, msg):
            raise OptParseError(msg)
        def exit(self, status=0, msg=None):
            raise Exit(status, msg)
    try:
        __usage__ = ( "Usage: %s [-fvn]  [-r]  [-wl] [-s FORMAT] [-e EXPR]...\n"
                      "       %s [-i N] [-j N] [-z]  [FILE]..."
                      % (__prog__, len(__prog__)*' ') )
        parser = OptParser(prog=__prog__, version="%prog "+__version__,
                           usage=__usage__, add_help_option=False)
        parser.add_option("-h", "--help", default=False, action="store_true",
                          help='show this help message and exit')
        parser.add_option("-?", "--usage", default=False, action="store_true",
                          help='show a brief usage string and exit')
        parser.add_option("-f", "--force", default=False, action="store_true",
                          help='overwrite existing files')
        parser.add_option("-v", "--verbose", default=False, action="store_true",
                          help='print names of files successfully renamed')
        parser.add_option("-n", "--no-act", default=False, action="store_true",
                          help='only show which files would be renamed')
        parser.add_option("-r", "--stdin", default=False, action="store_true",
                          help='read destination paths verbatim from standard '
                               'input, one per line, and match them up with the '
                               'command-line arguments (all the renaming options '
                               'below will be ignored); an empty line means to '
                               'skip the corresponding argument')
        parser.add_option("-w", "--whole-name", default=False, action="store_true",
                          help='change the entire name (by default, any file '
                               'suffix is automatically preserved)')
        parser.add_option("-l", "--lower-extension", default=False, action="store_true",
                          help='if not changing the entire name, cast all '
                               'extensions to lower case')
        if number:
            default_fmt = _fmt_number
        else:
            default_fmt = _fmt_name
        parser.add_option("-s", "--format", metavar="FORMAT", default=default_fmt,
                          help='format string for new names, in which "' +
                               _fmt_name + '" is replaced by the original file '
                               'name and "' + _fmt_number + '" by an incremental '
                               'number (see "Numbering" below); for example, '
                               '--format="' + _fmt_number + '-' + _fmt_name + '" '
                               'or -s "00{N}" (the default is "%default")')
        parser.add_option("-e", "--expression", metavar="EXPR",
                          default=[], action="append",
                          help='one or more semicolon-separated transformations '
                               'to be run on each file name, in sequence, before '
                               'the above FORMAT substitution. Each may be a '
                               'Python regular expression substitution (e.g. '
                               '\'s/^foo(\w{3})/boo\\1/g\') or a Perl-style trans'
                               'literation (e.g. \'y/A-Z/a-z/\'). Available flags '
                               'for s/// are "a" (see re.ASCII), "i" (case-'
                               'insensitive pattern), "g" (replace all), and N > 0 '
                               '(replace up to N occurrences); available flags '
                               'for y/// are the same as in Perl: "c" (complement '
                               'the search list), "d" (delete characters in the '
                               'search list not found in the replacement list), '
                               'and "s" (squash runs of replaced characters). '
                               'N.B. unless the -w option is given, tranformations '
                               'are only performed on the part of the name before '
                               'the extension, if any')
        group = OptionGroup(parser, "Numbering")
        group.add_option("-i", "--initial", metavar="N", default=1, type="int",
                          help='index for the first file (default is %default)')
        group.add_option("-j", "--increment", metavar="N", default=1, type="int",
                          help='increment for each successive file; may be '
                               'negative (default is %default)')
        group.add_option("-z", "--zero-pad", default=False, action="store_true",
                          help='use leading zeros to pad numbers')
        parser.add_option_group(group)
        opts, args = parser.parse_args(argv[1:])

        if opts.help:
            parser.print_version()
            if number:
                print(__num__ % globals())
            else:
                print(__doc__ % globals())
            print()
            parser.print_help()
            raise Exit(0, None)
        elif opts.usage:
            parser.print_usage()
            raise Exit(0, None)

        _force = opts.force
        _verbose = opts.verbose
        _noact = opts.no_act
        _stdin = opts.stdin
        _wname = opts.whole_name
        _lower = opts.lower_extension

        _format = opts.format
        if not _format:
            raise OptParseError("empty format string")

        _do_fmt_name = bool(_re_fmt_name.search(_format))
        _do_fmt_number = bool(_re_fmt_number.search(_format))

        _transform = StringTransform()
        for expr in opts.expression:
            try:
                _transform.addOperations(expr)
            except StringTransform.ParseError as e:
                raise OptParseError(': '.join(e.args))

        _counter = opts.initial
        _increment = opts.increment
        _zpad = opts.zero_pad

        return args

    except OptParseError as e:
        parser.print_usage(file=sys.stderr)
        raise Exit(2, e.msg)

def main(argv=None):
    if argv is None:
        argv = sys.argv

    signals = ("SIGINT", "SIGQUIT", "SIGABRT", "SIGHUP", "SIGTERM")
    saved_handlers = {}
    for signame in signals:
        signum = getattr(signal, signame, None)
        if signum:
            saved_handlers[signum] = signal.signal(signum, handler)
    try:
        global __prog__
        __prog__ = path.basename(argv[0])

        updateStatus(0)
        instantiateGlobals()

        global _queue
        _queue = generateRenames(parseOptions(argv))

        if not _noact:
            for rn in _queue: rn.tempMove()
            for rn in _queue: rn.doRename()

        for rn in _queue: rn.print()
        return _status

    except Exit as e:
        PrintError(*e.args)
        return e.status

    finally:
        try:
            for rn in _queue:
                rn.tempRevert()
        except NameError:
            pass

        for signum in saved_handlers:
            signal.signal(signum, saved_handlers[signum])


if __name__ == '__main__':
    sys.exit(main())

