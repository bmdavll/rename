=============
``rename.py``
=============

--------------------------------
Rename files on the command line
--------------------------------

``rename.py`` is a general purpose renamer written in Python 3. Among other
features, it can number files on the command line in argument order. This is
the default mode if the script is run with "*num*" as part of its name.

Safe reorderings are allowed. For example ``renumb.py 2.jpg 1.jpg`` swaps
the two file names, and ``renumb.py 1.jpg 1a.jpg 2.jpg`` succeeds in
renaming the last two files (to ``2.jpg`` and ``3.jpg`` respectively) only
if ``3.jpg`` doesn't exist.


Usage
-----
::

  rename.py [-fvn]  [-r]  [-wl] [-s FORMAT] [-e EXPR]...
            [-i N] [-j N] [-z]  [FILE]...

Options
-------
::

  --version             show program's version number and exit
  -h, --help            show this help message and exit
  -?, --usage           show a brief usage string and exit
  -f, --force           overwrite existing files
  -v, --verbose         print names of files successfully renamed
  -n, --no-act          only show which files would be renamed
  -r, --stdin           read destination paths verbatim from standard input,
                        one per line, and match them up with the command-line
                        arguments (all the renaming options below will be
                        ignored); an empty line means to skip the
                        corresponding argument
  -w, --whole-name      change the entire name (by default, any file suffix is
                        automatically preserved)
  -l, --lower-extension
                        if not changing the entire name, cast all extensions
                        to lower case
  -s FORMAT, --format=FORMAT
                        format string for new names, in which "{}" is replaced
                        by the original file name and "{N}" by an incremental
                        number (see "Numbering" below); for example,
                        --format="{N}-{}" or -s "00{N}" (the default is "{}")
  -e EXPR, --expression=EXPR
                        one or more semicolon-separated transformations to be
                        run on each file name, in sequence, before the above
                        FORMAT substitution. Each may be a Python regular
                        expression substitution (e.g. 's/^foo(\w{3})/boo\1/g')
                        or a Perl-style transliteration (e.g. 'y/A-Z/a-z/').
                        Available flags for s///:
                            a       make \w, \b, \d, \s, etc. perform ASCII-
                                    only matching
                            i       case-insensitive pattern
                            g       replace all occurrences
                            N > 0   replace up to N occurrences
                        Available flags for y///: (same as in Perl)
                            c       complement the search list
                            d       delete found but unreplaced characters
                            s       squash duplicate replaced characters
                        N.B. unless the -w option is given, tranformations are
                        only performed on the part of the name before the
                        extension, if any.

  Numbering:
    -i N, --initial=N   index for the first file (default is 1)
    -j N, --increment=N
                        increment for each successive file; may be negative
                        (default is 1)
    -z, --zero-pad      use leading zeros to pad numbers


Author
======

David Liang (bmdavll at gmail.com)

