# SPDX-License-Identifier: Apache-2.0
"""Plumbing for git surface: records, arguments, errors and running git.

Everything that crosses a process boundary (stdin, stdout, git's output) is bytes. Text is
decoded only to build a message for stderr or to look for characters in an added line.
"""

import errno
import os
import re
import subprocess
import sys

from . import __version__

EXIT_NOTHING = 0  # ran, nothing found
EXIT_FOUND = 1  # ran, something found
EXIT_ERROR = 2  # error

# One object id: 40 hex digits (SHA-1) or 64 (SHA-256). \A and \Z, because $ also matches
# before a trailing LF.
OID = re.compile(rb"\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")

_ESCAPES = {0x09: "\\t", 0x0A: "\\n", 0x0D: "\\r", 0x5C: "\\\\"}


class Fail(Exception):
    """A user-facing error: `run` prints `git-surface: <message>` and exits 2."""


class PipeClosed(Exception):
    """The reader of stdout went away; `run` exits 0 quietly."""


def show(data):
    """Escape a name for an error message so it stays one line of printable ASCII.

    Args:
        data: bytes (from a record or git) or str (from the command line).

    Returns:
        A str: TAB, LF, CR and backslash as backslash escapes, other unprintable bytes as \\xHH.
    """
    if not isinstance(data, bytes):
        data = os.fsencode(data)
    out = []
    for byte in bytearray(data):
        if byte in _ESCAPES:
            out.append(_ESCAPES[byte])
        elif 0x20 <= byte < 0x7F:
            out.append(chr(byte))
        else:
            out.append("\\x%02x" % byte)
    return "".join(out)


def parse_args(argv, flags):
    """Split argv into flags and positionals; anything that is not a known flag is positional.

    A ref that starts with "-" is therefore a ref. "--" ends option parsing.

    Args:
        argv: The arguments, without the program name.
        flags: The options the command knows, none of which takes a value.

    Returns:
        A tuple ({flag: True}, [positionals]).
    """
    opts = {}
    positionals = []
    for i, arg in enumerate(argv):
        if arg == "--":
            positionals.extend(argv[i + 1:])
            break
        if arg in flags:
            opts[arg] = True
        else:
            positionals.append(arg)
    return opts, positionals


def read_records(zero):
    """Read all of stdin and return its non-empty records with their numbers.

    LF mode splits on LF and removes one trailing CR; -z mode splits on NUL. Numbers count
    every record from 1, skipped empty ones included, like line numbers.

    Args:
        zero: True for NUL-terminated records.

    Returns:
        A list of (record number, record bytes).

    Raises:
        Fail: Standard input is not open.
    """
    if sys.stdin is None:
        raise Fail("standard input is not open")
    data = sys.stdin.buffer.read()
    parts = data.split(b"\0" if zero else b"\n")
    # A final terminator leaves one empty tail; an unterminated last record is kept.
    if parts and parts[-1] == b"":
        parts.pop()
    records = []
    for number, record in enumerate(parts, 1):
        if not zero and record.endswith(b"\r"):
            record = record[:-1]
        if record:
            records.append((number, record))
    return records


def check_safe(field, zero, what):
    """Fail if FIELD cannot be written in an LF record (it holds TAB, LF or CR).

    Args:
        field: The ref or path, as bytes.
        zero: True in -z mode, where every field is safe.
        what: "ref" or "path", for the message.

    Raises:
        Fail: The field is unsafe in LF mode; the message names -z.
    """
    if zero:
        return
    if b"\t" in field or b"\n" in field or b"\r" in field:
        raise Fail("%s contains TAB, LF or CR and cannot be written as a line; use -z: %s"
                   % (what, show(field)))


def write_stdout(data):
    """Write bytes to stdout, or flush it when DATA is None.

    Raises:
        PipeClosed: The reader closed the pipe (EPIPE; EINVAL on Windows).
    """
    try:
        if data is None:
            sys.stdout.flush()
        else:
            sys.stdout.buffer.write(data)
    except OSError as exc:
        if isinstance(exc, BrokenPipeError) or exc.errno in (errno.EPIPE, errno.EINVAL):
            raise PipeClosed()
        raise


_TERMINAL = []


def _stdout_is_terminal():
    """Return True if stdout is a terminal; asked once per process."""
    if not _TERMINAL:
        try:
            _TERMINAL.append(bool(sys.stdout.isatty()))
        except (OSError, ValueError):
            _TERMINAL.append(False)
    return _TERMINAL[0]


def for_terminal(field):
    """Return FIELD with every byte a terminal could act on written as an escape.

    C0 controls, DEL, C1 controls and bytes that are not valid UTF-8 become \\xHH, one per
    byte; a backslash is doubled. Printable UTF-8 passes through.

    Args:
        field: bytes.

    Returns:
        bytes.
    """
    out = []
    for char in field.decode("utf-8", "surrogateescape"):
        code = ord(char)
        if char == "\\":
            out.append("\\\\")
        elif 0xDC80 <= code <= 0xDCFF:
            # surrogateescape maps an invalid byte B to U+DC00 + B.
            out.append("\\x%02x" % (code - 0xDC00))
        elif code < 0x20 or 0x7F <= code <= 0x9F:
            out.extend("\\x%02x" % byte for byte in char.encode("utf-8"))
        else:
            out.append(char)
    return "".join(out).encode("utf-8")


def write_record(fields, zero):
    """Write one TAB-separated record ending in LF, or NUL with -z.

    In LF mode on a terminal each field goes through `for_terminal`; pipes, files and -z
    output carry the raw bytes.
    """
    if not zero and _stdout_is_terminal():
        fields = [for_terminal(field) for field in fields]
    write_stdout(b"\t".join(fields) + (b"\0" if zero else b"\n"))


def git(args):
    """Run git with list arguments (never a shell) and LC_ALL=C.

    Args:
        args: The arguments after "git", str or bytes.

    Returns:
        (exit code, stdout bytes, stderr bytes).

    Raises:
        Fail: git cannot be run, or (on Windows) an argument is not valid UTF-8.
    """
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    argv = ["git"]
    for arg in args:
        if isinstance(arg, bytes):
            try:
                arg = os.fsdecode(arg)
            except UnicodeDecodeError:
                raise Fail("cannot pass a name that is not valid UTF-8 to git on this "
                           "platform: %s" % show(arg))
        argv.append(arg)
    try:
        proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env)
    except OSError as exc:
        raise Fail("cannot run git: %s" % exc)
    return proc.returncode, proc.stdout, proc.stderr


def git_error(stderr, code):
    """Describe a git failure in one escaped line."""
    lines = stderr.strip().splitlines()
    if lines:
        return show(lines[0])
    return "git exited with status %d" % code


def resolve(ref):
    """Return the commit id REF names.

    `rev-parse --verify` must print exactly one object id (this rejects ranges and "^a"),
    and that id must peel to a commit. --end-of-options keeps a ref starting with "-" a ref.

    Raises:
        Fail: REF is unknown or not a commit.
    """
    error = Fail("unknown ref or not a commit: %s" % show(ref))
    code, out, _ = git(["rev-parse", "--verify", "--quiet", "--end-of-options", ref])
    oid = out[:-1] if out.endswith(b"\n") else out
    if code != 0 or not OID.match(oid):
        raise error
    code, out, _ = git(["rev-parse", "--verify", "--quiet", oid + b"^{commit}"])
    sha = out.strip()
    if code != 0 or not OID.match(sha):
        raise error
    return sha


def usage_and_version(opts, usage):
    """Print usage for -h or the version for --version; return True if one was handled."""
    if opts.get("-h"):
        write_stdout((usage + "\n").encode("ascii"))
        return True
    if opts.get("--version"):
        write_stdout(("git-surface %s\n" % __version__).encode("ascii"))
        return True
    return False


def error(message):
    """Write `git-surface: <message>` to stderr as one line ending in LF."""
    if sys.stderr is None:
        return
    text = "git-surface: %s\n" % str(message).replace("\r", "\\r").replace("\n", "\\n")
    sys.stderr.flush()
    stream = getattr(sys.stderr, "buffer", None)
    if stream is None:
        sys.stderr.write(text)
        sys.stderr.flush()
        return
    stream.write(text.encode(getattr(sys.stderr, "encoding", None) or "utf-8",
                             "backslashreplace"))
    stream.flush()


def _discard_stdout():
    """Point file descriptor 1 at the null device so the exit-time flush cannot fail."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())


def run(body):
    """Call body() and exit with its code; turn every failure into one line and exit 2.

    A closed stdout pipe is a quiet exit 0; Ctrl-C is exit 130; never a traceback.
    """
    if sys.stdout is None:
        error("standard output is not open")
        sys.exit(EXIT_ERROR)
    try:
        code = body()
        write_stdout(None)
    except Fail as exc:
        error(exc)
        code = EXIT_ERROR
    except KeyboardInterrupt:
        code = 128 + 2
    except PipeClosed:
        _discard_stdout()
        code = EXIT_NOTHING
    except Exception as exc:  # noqa: BLE001 - one line, never a traceback
        error("internal error: %s" % exc)
        code = EXIT_ERROR
    sys.exit(code)
