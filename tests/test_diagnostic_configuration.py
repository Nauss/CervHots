"""Constructor/configuration regressions; never contact the gateway."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cerveau import diagnostic_session as session


class ConfigurationTests(unittest.TestCase):
    def test_preflight_refuses_missing_coach_configuration_before_source(self):
        output = StringIO()
        with patch.object(session, 'preflight', return_value={'ready': True}), \
                patch.object(session, 'configured_coach', side_effect=ValueError('PRIVATE_SECRET')), \
                patch('cerveau.__main__.make_source') as source, redirect_stdout(output):
            result = session.main([])
        self.assertEqual(result, 1)
        self.assertFalse(json.loads(output.getvalue())['ready'])
        self.assertNotIn('PRIVATE_SECRET', output.getvalue())
        source.assert_not_called()

    def test_explicit_runtime_config_constructs_coach_without_chat_or_secret_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'runtime.conf'
            config.write_text('GROCO_MODEL=fixture-model\nGROCO_API_TOKEN=PRIVATE_SECRET\n'
                              'GROCO_API_URL=https://fixture.invalid\n'
                              'GROCO_REASONING_EFFORT=low\n', encoding='utf-8')
            with patch.dict(os.environ, {}, clear=True), patch('grocoapi.GrocoClient.chat') as chat:
                coach = session.configured_coach(config)
        self.assertEqual(coach.model, 'fixture-model')
        self.assertEqual(coach.reasoning_effort, 'low')
        self.assertEqual(coach.client.base_url, 'https://fixture.invalid')
        self.assertEqual(coach.client.token, 'PRIVATE_SECRET')
        self.assertEqual(coach.min_confidence, 0.75)
        chat.assert_not_called()


if __name__ == '__main__':
    unittest.main()
