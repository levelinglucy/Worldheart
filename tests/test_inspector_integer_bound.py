"""Bound JSON numeric-token cost while inspecting untrusted synthetic envelopes."""
import contextlib
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

INSPECTOR = Path(__file__).resolve().parents[1] / 'inspect_checkpoint.py'
spec = importlib.util.spec_from_file_location('worldheart_inspector', INSPECTOR)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(seed_digits, extra=''):
    payload = b'disposable sample, not a pickle'
    envelope = '{"version":"0.2.1","seed":%s,"tick":12,"payload":"%s","hash":"%s"%s}' % (
        seed_digits, payload.hex(), hashlib.blake2b(payload, digest_size=8).hexdigest(), extra)
    return envelope.encode('ascii')


@contextlib.contextmanager
def unrestricted_runtime_integer_parser():
    # Only the test process changes its own interpreter limit temporarily.
    original = sys.get_int_max_str_digits() if hasattr(sys, 'get_int_max_str_digits') else None
    try:
        if original is not None:
            sys.set_int_max_str_digits(0)
        yield
    finally:
        if original is not None:
            sys.set_int_max_str_digits(original)


class NumericTokenBoundTests(unittest.TestCase):
    def test_oversized_seed_refused_with_int_parser_limit_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'large.wh'
            data = fixture('9'*5000)
            p.write_bytes(data)
            with unrestricted_runtime_integer_parser():
                with self.assertRaisesRegex(ValueError, 'integer exceeds'):
                    module.inspect(p)
            self.assertEqual(p.read_bytes(), data)

    def test_oversized_unknown_field_also_refused_before_discard(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'extra.wh'
            data = fixture('7', ',"unneeded":'+'8'*5000)
            p.write_bytes(data)
            with unrestricted_runtime_integer_parser():
                with self.assertRaisesRegex(ValueError, 'integer exceeds'):
                    module.inspect(p)
            self.assertEqual(p.read_bytes(), data)

    def test_within_bound_and_pair_semantics_remain(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d)/'a.wh', Path(d)/'b.wh'
            a.write_bytes(fixture('7'))
            b.write_bytes(fixture('7').replace(b'"tick":12',b'"tick":20'))
            left = module.inspect(a)
            right = module.inspect(b)
            self.assertEqual(left['status'], 'checksum_matches')
            self.assertEqual(module.compare_inspections(left, right)['second_minus_first_tick'], 8)
            self.assertEqual(a.read_bytes(),fixture('7'))
            self.assertEqual(b.read_bytes(),fixture('7').replace(b'"tick":12',b'"tick":20'))


if __name__ == '__main__':
    unittest.main()
