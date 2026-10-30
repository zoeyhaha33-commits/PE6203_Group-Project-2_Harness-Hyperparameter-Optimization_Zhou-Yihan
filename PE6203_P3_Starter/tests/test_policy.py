from src.harness_adapter import demo_task, official_task
from src.experiment import evaluate
import pytest

def test_deterministic():
    c={'steps':10,'retries':1,'context':'medium'}
    assert demo_task(c,4)==demo_task(c,4)

def test_no_fake_official_results():
    with pytest.raises(NotImplementedError):
        official_task({},1)

def test_evaluation():
    c={'steps':10,'retries':1,'context':'medium'}
    v=evaluate(c,[0,1,2],demo_task,42)
    assert 0<=v['pass_at_1']<=1 and v['task_count']==3
