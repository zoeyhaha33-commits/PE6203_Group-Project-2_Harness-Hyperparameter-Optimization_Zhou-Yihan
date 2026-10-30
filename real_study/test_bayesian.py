"""TPE scheduling/replay checks with synthetic outcomes, never model calls."""
import json
import unittest
from unittest.mock import patch

import optuna
import run_search as runner


class BayesianReplayTests(unittest.TestCase):
    def simulate(self, resume, missing=False):
        protocol = {'seed': 20261028}
        state = runner.initial_state('bayesian', protocol)
        pairs = []
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('No paid tasks')):
            for number in range(9):
                if resume:
                    state = json.loads(json.dumps(state))
                candidate, task = runner.next_pair(state, protocol)
                pairs.append((candidate, task))
                skipped = missing and number == 1
                state['records'].append({'candidate': candidate, 'task_index': task,
                    'status': 'skipped_api_failure' if skipped else 'complete',
                    'reward': None if skipped else float(task == candidate),
                    'strict_pass': None if skipped else task == candidate,
                    'cost_usd': None if skipped else .02})
            self.assertIsNone(runner.next_pair(state, protocol))
        self.assertEqual(len(set(pairs)), 9)
        self.assertEqual(len(state['configs']), 3)
        self.assertEqual(state['optuna_version'], '4.5.0')
        return state

    def test_resume_matches_uninterrupted(self):
        self.assertEqual(self.simulate(True), self.simulate(False))

    def test_missing_trial_replay_matches(self):
        self.assertEqual(self.simulate(True, True), self.simulate(False, True))


if __name__ == '__main__':
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    unittest.main()
