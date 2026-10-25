"""CLI migration contracts. SYNTHETIC transports are not live qualification."""
from contextlib import redirect_stdout
import inspect
import io
import json
import unittest
from unittest.mock import patch

from cerveau import passive_session as product


class DefaultCollectionTests(unittest.TestCase):
    def test_preflight_reports_effective_selection_without_creating_source(self):
        for selection in (None, 'core', 'all', 'talents'):
            args = [] if selection is None else ['--preflight', '--collection', selection]
            effective = selection or 'core'
            output = io.StringIO()
            with self.subTest(selection=selection), redirect_stdout(output), \
                    patch.object(product, 'NativeSource', side_effect=AssertionError('source forbidden')), \
                    patch.object(product, 'preflight', return_value={'event':'preflight','ready':True}) as check:
                self.assertEqual(product.main(args), 0)
            self.assertEqual(check.call_args.kwargs, {'core':True} if effective == 'core' else {})
            row = json.loads(output.getvalue())
            self.assertEqual(row['collection'], effective)
            self.assertEqual(row['not_selected'], product.measured_acquisition({'collection':effective})['not_selected'])

    def test_synthetic_real_cli_default_opt_ins_stop_and_fresh_restart(self):
        import tempfile
        from pathlib import Path
        from tests.helpers.default_collection_synthetic import exercise
        with tempfile.TemporaryDirectory() as directory:
            results = exercise(Path(directory)/'SYNTHETIC')
        self.assertEqual([r['collection'] for r in results], ['core', 'core', 'all', 'talents'])

    def test_public_source_and_preflight_defaults_remain_legacy_compatible(self):
        self.assertEqual(inspect.signature(product.NativeSource).parameters['collection'].default, 'all')
        self.assertIs(inspect.signature(product.preflight).parameters['core'].default, False)
