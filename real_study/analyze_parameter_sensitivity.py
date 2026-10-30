"""Exploratory matched-parameter comparisons using existing validation only."""
from collections import defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent


def main():
    protocol = json.loads((ROOT / 'final_test_protocol.json').read_text())
    groups, missing, seen = defaultdict(list), [], set()
    for method in ('random', 'bayesian', 'multifidelity'):
        path = ROOT / f'{method}_state.json'
        if hashlib.sha256(path.read_bytes()).hexdigest() != protocol['search_state_sha256'][method]:
            raise RuntimeError('Frozen validation ledger changed: ' + method)
        state = json.loads(path.read_text())
        for row in state['records']:
            config = state['configs'][row['candidate']]
            if row['jobs_dir'] in seen:
                raise RuntimeError('Duplicate validation job.')
            seen.add(row['jobs_dir'])
            if row['status'] != 'complete':
                missing.append(dict(method=method, task=row['task'], config=config, status=row['status']))
                continue
            groups[(row['task'], config['contextWindow'], config['maxTokens'])].append(dict(
                method=method, reward=row['reward'], passed=row['strict_pass'], cost=row['cost_usd']))
    cells = []
    for (task, context, tokens), rows in sorted(groups.items()):
        cells.append(dict(task=task, contextWindow=context, maxTokens=tokens, n=len(rows),
                          passes=sum(r['passed'] is True for r in rows),
                          pass_rate=mean(r['passed'] is True for r in rows),
                          mean_observed_usd=mean(r['cost'] for r in rows)))
    pairs = []
    for a, b in combinations(cells, 2):
        if a['task'] != b['task']:
            continue
        changed = [key for key in ('contextWindow', 'maxTokens') if a[key] != b[key]]
        if len(changed) != 1:
            continue
        key = changed[0]
        a, b = sorted((a, b), key=lambda r: r[key])
        fixed = 'maxTokens' if key == 'contextWindow' else 'contextWindow'
        pairs.append(dict(task=a['task'], parameter=key, fixed_parameter=fixed, fixed_value=a[fixed],
            lower=a, upper=b, pass_rate_delta=b['pass_rate']-a['pass_rate'],
            mean_usd_delta=b['mean_observed_usd']-a['mean_observed_usd']))
    lines = ['# 参数敏感性探索分析', '',
        '使用已有验证阶段记录，对同一任务、另一个参数固定的配置进行比较。没有新增模型调用，没有使用测试得分选参。这是事后探索性敏感性分析，不是独立随机化消融实验。', '',
        f'共 {sum(c["n"] for c in cells)} 条有效验证记录，{len(missing)} 条缺失，{len(pairs)} 组仅改变一个参数的配置对。重复配置按任务汇总为均值，n 表示有效运行数；缺失不填 0。', '',
        '| 任务 | contextWindow | maxTokens | n | 通过 / n | 平均观察费用 USD |',
        '|---|---:|---:|---:|---:|---:|']
    for c in cells:
        lines.append(f"| {c['task']} | {c['contextWindow']} | {c['maxTokens']} | {c['n']} | {c['passes']} / {c['n']} | {c['mean_observed_usd']:.8f} |")
    lines += ['', '## 单参数对比', '',
        '| 任务 | 改变的参数 | 固定参数 | 低值 → 高值 | n 低 / 高 | 通过率差 高减低 | 平均费用差 USD 高减低 |',
        '|---|---|---|---|---:|---:|---:|']
    for p in pairs:
        key=p['parameter']; a=p['lower']; b=p['upper']
        lines.append(f"| {p['task']} | {key} | {p['fixed_parameter']}={p['fixed_value']} | {a[key]} → {b[key]} | {a['n']} / {b['n']} | {100*p['pass_rate_delta']:+.1f} 个百分点 | {p['mean_usd_delta']:+.8f} |")
    lines += ['', '## 解读与限制', '',
        '- 这些差值描述观察关联，不能排除方法、运行时间、模型随机性和计费差额的影响。每个配置的重复数不等，未将不同验证任务的通过率直接混合后用于参数排名。',
        '- 在 financial-modeling-qa 上所有已评分配置均未通过；现有参数变化未观察到成功率改善。在其他任务上的少数通过来自很少的重复，不能证明单个参数稳定提高成功率。',
        '- cost 是已评分记录的观察费用均值；缺失区间与恢复启动费用仍由总表单独记账，不算作成功或精确单任务费用。',
        '- 当前不能可靠判定哪个参数对成功率最重要；费用差异也不能仅归因于参数。报告应展示对比表和不确定性，而不是宣称完成了因果归因。',
        '- 若需更强结论，另立仅使用验证任务的补充实验：固定模型和其他条件，使用 2×2 参数网格（contextWindow=64000/128000，maxTokens=4096/16384），每格相同任务和重复数；预先约定费用、随机化运行次序、失败处理和停止条件。冻结的最终配置与测试结果不改变。', '']
    (ROOT / 'parameter_sensitivity.md').write_text('\n'.join(lines), encoding='utf-8')
    (ROOT / 'parameter_sensitivity.json').write_text(json.dumps(dict(scope='existing validation only; exploratory', cells=cells, pairs=pairs, missing=missing), indent=2)+'\n', encoding='utf-8')
    print(f'Validation-only sensitivity: {len(cells)} cells, {len(pairs)} matched comparisons, {len(missing)} missing records.')


if __name__ == '__main__':
    main()
