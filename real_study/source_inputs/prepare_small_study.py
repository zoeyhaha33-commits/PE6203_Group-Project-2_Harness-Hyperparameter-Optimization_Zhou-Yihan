"""Freeze a small resource-screened subset before observing evaluation outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import yaml


def make_plan(repo, shared):
    split = json.loads((shared / 'split_manifest.json').read_text(encoding='utf-8'))
    selected, audit = {}, []
    for partition in ('validation', 'test'):
        selected[partition] = []
        for entry in split[partition]:
            path = repo / 'tasks' / entry['name'] / 'task.md'
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry['definition_sha256']:
                raise ValueError('Task definition differs from frozen inventory: ' + entry['name'])
            text = raw.decode('utf-8')
            front = yaml.safe_load(text.split('---', 2)[1])
            resources = front.get('sandbox', front.get('environment', {}))
            timeout = front.get('agent', {}).get('timeout_sec')
            reasons = []
            for field, ceiling in [('cpus', 4), ('memory_mb', 4096), ('storage_mb', 10240), ('gpus', 0)]:
                value = resources.get(field)
                if not isinstance(value, (int, float)) or value > ceiling:
                    reasons.append(field + ' exceeds limit or is unspecified')
            if not isinstance(timeout, (int, float)) or timeout > 600:
                reasons.append('agent timeout exceeds 600 seconds or is unspecified')
            if not (path.parent / 'environment' / 'Dockerfile').is_file():
                reasons.append('no standard Dockerfile')
            audit.append({'partition': partition, 'name': entry['name'],
                          'resources': resources, 'agent_timeout_sec': timeout,
                          'excluded_reasons': reasons})
            if not reasons:
                selected[partition].append(dict(entry, resources=resources, agent_timeout_sec=timeout))
            if len(selected[partition]) == 3:
                break
        if len(selected[partition]) != 3:
            raise ValueError('Insufficient eligible tasks; no plan written')
    return {'status': 'small_study_subset_frozen_no_evaluations_started',
            'benchmark_commit': split['benchmark_commit'],
            'selection_rule': 'First 3 eligible tasks in each existing seeded partition; resource screening only, no evaluation outcomes.',
            'development_excluded': split['development_excluded'],
            **selected, 'resource_screening': audit,
            'fixed': {'harness': 'pi-acp', 'pi_version': '0.81.0', 'acp_version': '0.0.34',
                      'model': 'litellm/qwen/qwen3-coder', 'skill_mode': 'no-skill',
                      'loop_strategy': 'single-shot', 'concurrency': 1},
            'budget_allocations_usd': {'default_validation': 0.5, 'random_search': 1.5,
                                      'bayesian_search': 1.5, 'student_multifidelity_search': 1.5,
                                      'final_test_all_methods': 2.0},
            'budget_rules': ['These allocations are admission limits, not provider-enforced hard caps.',
                             'Recheck dedicated-key cumulative usage before and after each task; stop if accounting is unavailable.',
                             'Keep at least USD 2 unallocated for development costs, billing delays and overruns; total project allocation USD 10.',
                             'No automatic retries after infrastructure errors; retain failed and interrupted run records.'],
            'evaluation_rules': ['Freeze search space and optimizer stopping rules before validation runs.',
                                 'Select all four methods configurations before evaluating any held-out test task.',
                                 'Never select tasks or parameters based on test outcomes.',
                                 'Primary metric: strict whole-task pass@1; retain official partial reward separately.',
                                 'Three held-out tasks provide only a small exploratory comparison, not a precise benchmark estimate.',
                                 'Audit verification and cost capture before scaling to parameter search.'],
            'paid_tasks_started_by_this_script': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path.home() / 'pe6203-linux/skillsbench')
    args = parser.parse_args()
    shared = Path(__file__).resolve().parent
    plan = make_plan(args.repo, shared)
    target = shared / 'small_study_plan.json'
    encoded = json.dumps(plan, ensure_ascii=False, indent=2) + '\n'
    if target.exists() and target.read_text(encoding='utf-8') != encoded:
        raise SystemExit('Existing plan differs; refusing to replace frozen plan.')
    target.write_text(encoded, encoding='utf-8')
    for part in ('validation', 'test'):
        print(part + ': ' + ', '.join(t['name'] for t in plan[part]))
    print('Saved:', target)
    print('Paid tasks started: 0. No API key required.')


if __name__ == '__main__':
    main()
