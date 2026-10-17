"""Archives avec chat absent : cas réel des parties contre IA."""
import unittest
from unittest.mock import Mock

from hotstate import extract


class OptionalBlockTests(unittest.TestCase):
    def test_absent_or_empty_optional_events_are_not_decoded(self):
        self.assertTrue(callable(getattr(extract, "optional_events", None)))
        for payload in (None, b""):
            archive = Mock()
            archive.read_file.return_value = payload
            decoder = Mock()
            self.assertEqual(list(extract.optional_events(archive, "replay.message.events", decoder)), [])
            decoder.assert_not_called()

    def test_present_optional_block_is_passed_unchanged(self):
        self.assertTrue(callable(getattr(extract, "optional_events", None)))
        archive = Mock()
        archive.read_file.return_value = b"SYNTHETIC_TEST_BYTES"
        decoder = Mock(return_value=iter([{"type": "test"}]))
        self.assertEqual(list(extract.optional_events(archive, "test", decoder)), [{"type": "test"}])
        decoder.assert_called_once_with(b"SYNTHETIC_TEST_BYTES")
