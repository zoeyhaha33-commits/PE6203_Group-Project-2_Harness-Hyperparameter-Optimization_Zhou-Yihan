"""Strict boundary between teaching demo and official benchmark integration."""
import hashlib
import random


def demo_task(config, task_id: int, seed: int = 42):
    """Synthetic deterministic example. NEVER present as experimental benchmark evidence."""
    key = f'{config}|{task_id}|{seed}'
    rng = random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16))
    steps, retries, context = config['steps'], config['retries'], config['context']
    difficulty = (task_id * 7 % 13) / 12
    performance = 0.43 + min(steps, 15) * .015 + min(retries, 2) * .035 + {'small':-.07,'medium':0,'large':.045}[context] - difficulty * .22
    passed = int(rng.random() < max(.02, min(.96, performance)))
    cost = round((steps * .0008 + retries * .0015 + {'small':.003,'medium':.006,'large':.012}[context]) * (1 + difficulty * .2), 6)
    return {'passed': passed, 'usd': cost}


def official_task(config, task_id: int, seed: int = 42):
    """Not wired: must implement a real, official harness+benchmark runner here.

    Requirements: map only exposed actual Pi settings, execute the official
    SkillsBench task, read its unmodified verifier outcome, and calculate
    real measured provider cost. No fabricated success/cost fallback.
    """
    raise NotImplementedError('Official Pi + SkillsBench runner is NOT integrated. Follow README Real benchmark checklist.')
