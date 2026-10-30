"""Timeout recovery preserves official scores; no provider requests or launches."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_test


class TimeoutScoreTests(unittest.TestCase):
    def fixture(self, root, **changes):
        result = dict(task_name='task', error_category='timeout',
                      error='Agent prompt exceeded wall-clock budget 600s',
                      agent_timeout_info=dict(reason='wall_clock_timeout', timeout_sec=600,
                                              terminal_event_recorded=True),
                      n_tool_calls=13, verifier_error=None, rewards={'reward': 0.0})
        result.update(changes)
        raw = root / 'result.json'
        raw.write_text(json.dumps(result))
        state = root / 'test_random_state.json'
        state.write_text(json.dumps({'records': [dict(status='started', returncode=0,
            task='task', task_index=0, jobs_dir=str(root), result_paths=[str(raw)])]}))
        (root / 'final_test_protocol.json').write_text(json.dumps({
            'test': [{'name': 'task', 'agent_timeout_sec': 600.0}]}))
        return state

    def test_score_preserved_and_billing_resumable(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d, patch.object(run_test, 'ROOT', Path(d)):
            state = self.fixture(Path(d))
            original = state.read_bytes()
            run_test.prepare_timeout_billing(state)
            row = json.loads(state.read_text())['records'][0]
            self.assertEqual(row['status'], 'billing_pending')
            self.assertEqual(row['reward'], 0.0)
            self.assertFalse(row['strict_pass'])
            self.assertEqual(state.with_name('test_random_state.before_timeout_score.json').read_bytes(), original)
            run_test.prepare_timeout_billing(state)
            self.assertEqual(len(json.loads(state.read_text())['records']), 1)

    def test_invalid_results_leave_state_unchanged(self):
        for changes in ({'verifier_error': 'failed'}, {'rewards': None},
                        {'error_category': 'other'}, {'n_tool_calls': 0},
                        {'rewards': {'reward': 1.0}}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d, patch.object(run_test, 'ROOT', Path(d)):
                state = self.fixture(Path(d), **changes)
                original = state.read_bytes()
                with self.assertRaises(RuntimeError):
                    run_test.prepare_timeout_billing(state)
                self.assertEqual(state.read_bytes(), original)
                self.assertFalse((Path(d) / 'search.lock').exists())

    def test_command_timeout_is_missing_and_cost_is_retained(self):
        for values, expected in (([0.12] * 3, 'skipped_command_timeout'),
                                 ([0.12, 0.13, 0.14], 'run_failed')):
            with self.subTest(values=values), tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d, \
                 patch.object(run_test, 'ROOT', Path(d)), patch.object(run_test.runner, 'ROOT', Path(d)), \
                 patch('time.sleep'), patch.object(run_test.runner, 'usage', side_effect=values):
                state = self.fixture(Path(d), error='Command timed out after 900 seconds',
                                     agent_timeout_info=None, n_tool_calls=0, rewards=None)
                data = json.loads(state.read_text())
                data['records'][0].update(status='run_failed', returncode=1, key_usage_before_usd=0.1)
                state.write_text(json.dumps(data))
                if expected == 'run_failed':
                    with self.assertRaises(RuntimeError):
                        run_test.archive_build_failure(state, 'mock', command_timeout=True)
                else:
                    run_test.archive_build_failure(state, 'mock', command_timeout=True)
                row = json.loads(state.read_text())['records'][0]
                self.assertEqual(row['status'], expected)
                if expected != 'run_failed':
                    self.assertIsNone(row['reward'])
                    self.assertAlmostEqual(row['unattributed_interval_usd'], 0.02)
                    self.assertTrue(run_test.runner.resolved(row))
                self.assertFalse((Path(d) / 'search.lock').exists())


if __name__ == '__main__':
    unittest.main()
