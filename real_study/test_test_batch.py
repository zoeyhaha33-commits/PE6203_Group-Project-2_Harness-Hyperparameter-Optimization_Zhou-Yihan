"""Batch safety checks, using mocked task launches only."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import run_test_batch as batch


class BatchTests(unittest.TestCase):
    def test_failed_task_stops_batch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d, patch.object(batch, 'ROOT', Path(d)), \
             patch.object(batch.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'mock')) as launch:
            with self.assertRaises(subprocess.CalledProcessError):
                batch.run_batch('default')
            self.assertEqual(launch.call_count, 1)

    def test_resume_runs_only_remaining_slot(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d, patch.object(batch, 'ROOT', Path(d)):
            p = Path(d) / 'test_default_state.json'
            p.write_text(json.dumps({'records': [{'status': 'complete'}] * 2}))
            def launch(*args, **kwargs):
                p.write_text(json.dumps({'records': [{'status': 'complete'}] * 3}))
            with patch.object(batch.subprocess, 'run', side_effect=launch) as mock:
                batch.run_batch('default')
                self.assertEqual(mock.call_count, 1)

    def test_unresolved_record_prevents_launch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d, patch.object(batch, 'ROOT', Path(d)):
            (Path(d) / 'test_default_state.json').write_text(json.dumps({'records': [{'status': 'run_failed'}]}))
            with patch.object(batch.subprocess, 'run') as launch:
                with self.assertRaises(RuntimeError):
                    batch.run_batch('default')
                launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()

