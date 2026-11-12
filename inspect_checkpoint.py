"""Read-only Worldheart envelope and pair inspector; never unpickles saves.

This is a bounded diagnostic for untrusted checkpoint *metadata*, not a validator
of safe world objects, source authenticity, or recoverability.
"""

import argparse
import hashlib
import hmac
import json
import os
import stat
import sys

MAX_FILE_BYTES = 16 * 1024 * 1024
# Bound decimal-to-int conversion even on Python runtimes without a built-in cap.
MAX_JSON_INT_DIGITS = 4096


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate JSON field: %s" % key)
        out[key] = value
    return out


def _reject_constant(value):
    raise ValueError("Invalid JSON constant: %s" % value)


def _bounded_integer(value):
    # The JSON decoder calls this for every integer, including unused fields.
    # Avoid costly conversion of untrusted megabyte-scale integer literals.
    if len(value) - (1 if value.startswith("-") else 0) > MAX_JSON_INT_DIGITS:
        raise ValueError("Checkpoint JSON integer exceeds %d digits" % MAX_JSON_INT_DIGITS)
    return int(value)


def inspect(path):
    """Return limited envelope metadata without executing stored code or writing."""
    nofollow = getattr(os, "O_NOFOLLOW", None)
    nonblock = getattr(os, "O_NONBLOCK", None)
    if nofollow is None or nonblock is None:
        raise ValueError("Safe no-follow/nonblocking file open is unavailable")

    fd = os.open(path, os.O_RDONLY | nofollow | nonblock)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Checkpoint must be a direct, single-linked regular file")
        if info.st_size > MAX_FILE_BYTES:
            raise ValueError("Checkpoint exceeds the 16 MiB inspection limit")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            raw = stream.read(MAX_FILE_BYTES + 1)
    finally:
        if fd is not None:
            os.close(fd)

    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Checkpoint exceeds the 16 MiB inspection limit")
    envelope = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                          parse_constant=_reject_constant, parse_int=_bounded_integer)
    if not isinstance(envelope, dict):
        raise ValueError("Checkpoint envelope must be a JSON object")
    for key in ("version", "seed", "tick", "payload", "hash"):
        if key not in envelope:
            raise ValueError("Missing checkpoint field: %s" % key)
    version = envelope["version"]
    seed = envelope["seed"]
    tick = envelope["tick"]
    payload_hex = envelope["payload"]
    stored_hash = envelope["hash"]
    if not isinstance(version, str) or len(version) > 128:
        raise ValueError("Invalid checkpoint version")
    if type(seed) is not int or type(tick) is not int or tick < 0:
        raise ValueError("Invalid checkpoint seed or tick")
    if not isinstance(payload_hex, str) or not isinstance(stored_hash, str):
        raise ValueError("Invalid payload or hash field")
    if len(stored_hash) != 16 or any(c not in "0123456789abcdef" for c in stored_hash):
        raise ValueError("Invalid stored checksum format")
    try:
        payload = bytes.fromhex(payload_hex)
    except ValueError as exc:
        raise ValueError("Invalid hexadecimal payload") from exc
    actual = hashlib.blake2b(payload, digest_size=8).hexdigest()
    return {
        "status": "checksum_matches" if hmac.compare_digest(actual, stored_hash) else "checksum_mismatch",
        "version": version,
        "seed": seed,
        "tick": tick,
        "file_bytes": len(raw),
        "payload_bytes": len(payload),
        "warning": "Checksum is not authenticity or a guarantee of safe or recoverable pickle",
    }


def compare_inspections(first, second):
    """Compare outer recorded identity and ticks only when both checksums match.

    Even apparently matching envelopes cannot prove chronology or common ancestry.
    A bad checksum or different claimed seed/version suppresses tick ordering.
    """
    result = {
        "status": "not_comparable",
        "second_minus_first_tick": None,
        "higher_recorded_tick": None,
    }
    if first["status"] != "checksum_matches" or second["status"] != "checksum_matches":
        result["status"] = "checksum_mismatch"
    elif first["version"] != second["version"] or first["seed"] != second["seed"]:
        result["status"] = "different_recorded_identity"
    else:
        delta = second["tick"] - first["tick"]
        result["status"] = "same_recorded_identity"
        result["second_minus_first_tick"] = delta
        result["higher_recorded_tick"] = ("second" if delta > 0 else
                                           "first" if delta < 0 else "equal")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", help="Existing Worldheart .wh file to inspect without modification")
    parser.add_argument("--against", metavar="CHECKPOINT",
                        help="Optionally compare a second envelope without loading either pickle")
    args = parser.parse_args(argv)
    try:
        first = inspect(args.checkpoint)
        second = inspect(args.against) if args.against is not None else None
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print("Inspection refused: %s" % exc, file=sys.stderr)
        return 2
    if second is None:
        print(json.dumps(first, sort_keys=True))
        return 0 if first["status"] == "checksum_matches" else 1

    result = {
        "first": first,
        "second": second,
        "comparison": compare_inspections(first, second),
        "warning": (
            "Recorded tick order is not proof of chronology, shared lineage, "
            "authenticity, safe pickle loading or recoverability"
        ),
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if first["status"] == second["status"] == "checksum_matches" else 1


if __name__ == "__main__":
    sys.exit(main())
