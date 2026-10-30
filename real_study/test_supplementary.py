import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import run_supplementary_test as supplement


class SupplementTests(unittest.TestCase):
    def fixture(self, root):
        for name in ['final_test_protocol.json'] + [f'test_{m}_state.json' for m in ('default','random','bayesian','multifidelity')]:
            shutil.copyfile(Path(__file__).parent/name, root/name)

    def test_freeze_preserves_originals_and_rejects_changes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            root=Path(d)
            self.fixture(root)
            originals={p.name:p.read_bytes() for p in root.glob('*.json')}
            with patch.object(supplement,'ROOT',root), patch.object(supplement,'SUP',root/'supp'):
                first=supplement.freeze()
                self.assertEqual(supplement.freeze(),first)
                for name,raw in originals.items(): self.assertEqual((root/name).read_bytes(),raw)
                path=root/'test_random_state.json'
                path.write_bytes(path.read_bytes()+b'\n')
                with self.assertRaises(RuntimeError): supplement.freeze()

    def test_no_reward_is_never_zero(self):
        task={'name':'task','agent_timeout_sec':600}
        result={'task_name':'task','rewards':None,'error':'Command timed out after 900 seconds','error_category':'timeout'}
        self.assertIsNone(supplement.classify(result,task))
        self.assertEqual(supplement.classify(dict(task_name='task',rewards={'reward':0},error=None),task),0)
        self.assertIsNone(supplement.classify(dict(task_name='task',rewards={'reward':0},verifier_error='failure'),task))

    def test_scored_deadline_keeps_official_zero(self):
        task={'name':'task','agent_timeout_sec':600}
        r=dict(task_name='task',rewards={'reward':0},error_category='timeout',error='Agent prompt exceeded wall-clock budget 600s',
               agent_timeout_info=dict(reason='wall_clock_timeout',timeout_sec=600,terminal_event_recorded=True))
        self.assertEqual(supplement.classify(r,task),0)
        r['agent_timeout_info']['timeout_sec']=1200
        self.assertIsNone(supplement.classify(r,task))

    def test_consumed_slot_prevents_subprocess(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            root=Path(d); self.fixture(root)
            sup=root/'supp'; sup.mkdir()
            (sup/'default_state.json').write_text('{"records":[{"status":"started"}]}')
            with patch.object(supplement,'ROOT',root), patch.object(supplement,'SUP',sup), \
                 patch('sys.argv',['runner','--method','default','--execute','--exclusive-key']), \
                 patch.dict('os.environ',{'OPENROUTER_API_KEY':'mock'}), patch.object(supplement.subprocess,'run') as launch:
                with self.assertRaisesRegex(RuntimeError,'already consumed'): supplement.main()
                launch.assert_not_called()
                self.assertFalse((root/'search.lock').exists())


if __name__=='__main__': unittest.main()
