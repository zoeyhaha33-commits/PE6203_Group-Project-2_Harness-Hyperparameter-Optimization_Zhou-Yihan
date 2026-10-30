"""Offline recovery checks: mocked billing, no credentials or model calls."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_search as runner


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.directory.name).resolve()
        self.root_patch = patch.object(runner, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.root_patch.stop)
        self.protocol = {'validation': [{'name': 'example'}], 'seed': 1,
                         'usd_limit_per_method': 1.5, 'admission_reserve_usd': .2,
                         'key_usage_stop_usd': 7.75, 'task_limit_per_method': 9}
        self.path = self.root / 'random_state.json'
        self.result_path = self.root / 'jobs' / 'result.json'
        self.result_path.parent.mkdir()
        self.result = {'error_category': 'suspected_api_error', 'rewards': None,
                       'n_tool_calls': 0, 'task_name': 'example', 'verifier_error': None}
        runner.save(self.result_path, self.result)
        config = {'contextWindow': 96000, 'maxTokens': 4096}
        command = runner.command_for('bench', self.root, {'fixed': {'model': 'litellm/qwen/qwen3-coder'}},
                                     {'name': 'example'}, config, self.result_path.parent)
        self.state = {'method': 'random', 'configs': [config], 'records': [
            {'candidate': 0, 'task_index': 0, 'task': 'example', 'status': 'started',
             'returncode': 1, 'key_usage_before_usd': .3, 'jobs_dir': str(self.result_path.parent),
             'result_paths': [str(self.result_path)], 'command': command}]}
        runner.save(self.path, self.state)

    def recover(self, readings):
        with patch.object(runner, 'usage', side_effect=readings), patch.object(runner.time, 'sleep'), \
             patch.object(runner.subprocess, 'run', side_effect=AssertionError('Paid call forbidden')):
            runner.prepare_failed_retry(self.state, self.path, self.protocol, 'fake')

    def test_preserve_failure_and_same_pair(self):
        original = copy.deepcopy(self.state)
        self.recover([.3, .3, .3])
        self.assertEqual(runner.next_pair(self.state, self.protocol), (0, 0))
        self.assertEqual(self.state['configs'], original['configs'])
        self.assertEqual(self.state['failed_attempts'][0]['raw_result'], self.result)
        self.assertEqual(self.state['failed_attempts'][0]['cost_usd'], 0)
        self.assertEqual(runner.read(self.path.with_name('random_state.before_failed_retry.json')), original)
        with self.assertRaisesRegex(RuntimeError, 'already used'):
            self.recover([])

    def test_scoreable_failure_cannot_be_retried(self):
        self.result['rewards'] = {'reward': 0}
        runner.save(self.result_path, self.result)
        with self.assertRaisesRegex(RuntimeError, 'does not meet'):
            self.recover([])
        self.assertEqual(len(self.state['records']), 1)

    def test_docker_metadata_timeout_preserves_failure(self):
        self.result.update(error_category='other', sandbox_id=None,
                           trajectory_summary={'steps': 0}, agent_result={'total_tokens': 0},
                           error='Docker compose command failed build. Return code: 1. '
                                 'load metadata for docker.io/library/ubuntu:24.04 '
                                 'failed to authorize: DeadlineExceeded: context deadline exceeded')
        runner.save(self.result_path, self.result)
        self.recover([.3, .3, .3])
        self.assertEqual(self.state['failed_attempts'][0]['status'], 'archived_docker_build_failure')
        self.assertEqual(runner.next_pair(self.state, self.protocol), (0, 0))

    def test_docker_timeout_with_activity_or_different_error_is_rejected(self):
        base = dict(error_category='other', sandbox_id=None,
                    trajectory_summary={'steps': 0}, agent_result={'total_tokens': 0},
                    error='Docker compose command failed build. Return code: 1. '
                          'load metadata for docker.io/library/ubuntu:24.04 '
                          'failed to authorize: DeadlineExceeded: context deadline exceeded')
        for change in ({'agent_result': {'total_tokens': 1}}, {'trajectory_summary': {'steps': 1}},
                       {'sandbox_id': 'started'}, {'error': 'Docker build syntax error'}):
            self.assertFalse(runner.is_docker_build_timeout(dict(base, **change)))

    def test_unstable_billing_blocks_retry(self):
        with self.assertRaisesRegex(RuntimeError, 'not stable'):
            self.recover([.3, .31, .32])
        self.assertNotIn('failed_attempts', self.state)

    def test_failed_charge_is_included_in_next_budget_check(self):
        self.recover([1.6, 1.6, 1.6])
        self.assertAlmostEqual(runner.failed_cost(self.state), 1.3)
        self.state['records'] = [{'cost_usd': .1, 'status': 'complete'}]
        with patch.object(runner, 'usage', return_value=1.6), \
             patch.object(runner.subprocess, 'run', side_effect=AssertionError('Paid call forbidden')):
            with self.assertRaisesRegex(RuntimeError, 'Budget admission'):
                runner.run_task(self.state, self.protocol, (0, 0), self.root, 'bench', 'fake', self.path)

    def test_skip_preserves_missing_and_separates_diagnostic_spend(self):
        with patch.object(runner, 'usage', side_effect=[.31, .31, .31]), patch.object(runner.time, 'sleep'):
            runner.skip_failed(self.path, 'fake')
        state = runner.read(self.path)
        row = state['records'][0]
        self.assertEqual(row['status'], 'skipped_api_failure')
        self.assertIsNone(row['reward'])
        self.assertIsNone(row['cost_usd'])
        self.assertEqual(row['raw_result'], self.result)
        self.assertAlmostEqual(runner.accounted_cost(state), .01)
        self.assertEqual(runner.next_pair(state, self.protocol), (0, 1))
        self.assertEqual(runner.score(state, 0)[0], 0)
        with patch.object(runner, 'usage', side_effect=AssertionError('Idempotent skip must not query billing')):
            runner.skip_failed(self.path, 'fake')

    def test_skip_rejects_scoreable_failure(self):
        self.result['rewards'] = {'reward': 0}
        runner.save(self.result_path, self.result)
        with patch.object(runner, 'usage', side_effect=AssertionError('No billing query')):
            with self.assertRaisesRegex(RuntimeError, 'Only verified'):
                runner.skip_failed(self.path, 'fake')

    def test_skip_python_image_timeout_as_missing_without_retry(self):
        self.result.update(error_category='other', sandbox_id=None,
                           trajectory_summary={'steps': 0}, agent_result={'total_tokens': 0},
                           error='Docker compose command failed build. Return code: 1. '
                                 'load metadata for docker.io/library/python:3.12-slim '
                                 'failed to authorize: DeadlineExceeded: context deadline exceeded')
        runner.save(self.result_path, self.result)
        with patch.object(runner, 'usage', side_effect=[.3, .3, .3]), patch.object(runner.time, 'sleep'), \
             patch.object(runner.subprocess, 'run', side_effect=AssertionError('No task launch')):
            runner.skip_failed(self.path, 'fake')
        state = runner.read(self.path)
        self.assertEqual(state['records'][0]['status'], 'skipped_docker_failure')
        self.assertIsNone(state['records'][0]['reward'])
        self.assertTrue(runner.resolved(state['records'][0]))
        self.assertEqual(len(state['records']), 1)
        self.assertEqual(state['records'][0]['raw_result'], self.result)

    def test_ten_launch_cap_includes_archived_failure(self):
        state = {'records': [{'status': 'complete', 'cost_usd': .01}] * 9,
                 'failed_attempts': [{'cost_usd': 0}]}
        with patch.object(runner, 'usage', return_value=.5), patch.object(runner.subprocess, 'run', side_effect=AssertionError('No launch')):
            with self.assertRaisesRegex(RuntimeError, 'launch limit'):
                runner.run_task(state, self.protocol, (0, 0), self.root, 'bench', 'fake', self.path)


if __name__ == '__main__':
    unittest.main()
