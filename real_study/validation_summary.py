"""Summarize frozen validation ledgers separately from held-out scores."""
import hashlib
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run_search as runner


def build(root, protocol):
    data = {}
    for method in ('random', 'bayesian', 'multifidelity'):
        path = root / f'{method}_state.json'
        if hashlib.sha256(path.read_bytes()).hexdigest() != protocol['search_state_sha256'][method]:
            raise RuntimeError('Search ledger differs from frozen selection: ' + method)
        state = runner.read(path)
        rows = state['records']
        if len(rows) != 9 or any(not runner.resolved(r) for r in rows):
            raise RuntimeError('Unresolved search: ' + method)
        candidates = []
        for i, config in enumerate(state['configs']):
            own = [r for r in rows if r['candidate'] == i]
            scored = [r for r in own if r['status'] == 'complete']
            eligible = len(scored) == 3 and {r['task_index'] for r in scored} == {0, 1, 2}
            candidates.append(dict(candidate=i, config=config, scored=len(scored),
                missing=sum(r['status'] != 'complete' for r in own),
                passes=sum(r['strict_pass'] is True for r in scored), eligible=eligible,
                selected=i == state['selected']['candidate'],
                pass_rate=sum(r['strict_pass'] is True for r in scored) / 3 if eligible else None))
        curve = []
        spent = 0
        for n, row in enumerate(rows, 1):
            spent += (row['cost_usd'] if row['status'] == 'complete' else 0) + row.get('unattributed_interval_usd', 0)
            rates = []
            for i in range(len(state['configs'])):
                own = [r for r in rows[:n] if r['candidate'] == i and r['status'] == 'complete']
                if len(own) == 3 and {r['task_index'] for r in own} == {0, 1, 2}:
                    rates.append(sum(r['strict_pass'] is True for r in own) / 3)
            curve.append(dict(resolved_slots=n, best_complete_candidate_rate=max(rates) if rates else None,
                              cumulative_record_accounting_usd=spent))
        cost = runner.accounted_cost(state)
        if not math.isclose(cost, state['progress']['budget_accounted_usd'], abs_tol=1e-9):
            raise RuntimeError('Search accounting mismatch: ' + method)
        if not candidates[state['selected']['candidate']]['eligible']:
            raise RuntimeError('Selected candidate incomplete: ' + method)
        data[method] = dict(selected=state['selected'], candidates=candidates, curve=curve,
            valid=sum(r['status'] == 'complete' for r in rows),
            missing=sum(r['status'] != 'complete' for r in rows),
            launches=len(rows) + len(state.get('failed_attempts', [])),
            budget_accounted_usd=cost)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout='constrained')
    for method, s in data.items():
        x = [r['resolved_slots'] for r in s['curve']]
        axes[0].step([r['cumulative_record_accounting_usd'] for r in s['curve']], [r['best_complete_candidate_rate'] if r['best_complete_candidate_rate'] is not None else float('nan') for r in s['curve']],
                     where='post', marker='o', label=method)
        axes[1].plot(x, [r['cumulative_record_accounting_usd'] for r in s['curve']], marker='o', label=method)
    axes[0].set(title='Validation incumbent (complete candidates only)', ylabel='Strict pass rate', ylim=(-0.03, 0.4))
    axes[1].set(title='Validation observed accounting', ylabel='USD')
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.legend()
    axes[0].set_xlabel('Cumulative search accounting (USD)')
    axes[1].set_xlabel('Resolved validation slots (excludes extra retry launches)')
    axes[1].set_xticks(range(1, 10))
    fig.savefig(root / 'validation_search_curves.png', dpi=180)
    plt.close(fig)
    lines = ['', '## 验证阶段搜索整理', '',
        '验证题为 financial-modeling-qa、jax-computing-basics、travel-planning，与最终测试三题分离。以下验证分数用于选参，不是最终测试成绩。Default 未进行搜索，其历史真实验证基线在后面的独立章节列出。', '',
        '| 方法 | 候选记录数 / 不同配置数 | 有效评分 / 缺失 | 实际启动次数 | 入选候选 | contextWindow | maxTokens | 入选候选验证通过率 | 搜索记账 USD |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method, s in data.items():
        selected = s['selected']; config = selected['config']
        unique = len({tuple(sorted(c['config'].items())) for c in s['candidates']})
        lines.append(f"| {method} | {len(s['candidates'])} / {unique} | {s['valid']} / {s['missing']} | {s['launches']} | {selected['candidate']} | {config['contextWindow']} | {config['maxTokens']} | {selected['validation_pass_rate']:.1%} | {s['budget_accounted_usd']:.8f} |")
    lines += ['', '候选编号从 0 开始。三种搜索各有 9 个验证槽位；Random 和 Multifidelity 各有一次额外恢复启动、一次缺失。相同槽位上限不表示启动次数或实际费用相同。Bayesian 的三条候选记录使用同一配置，是独立重复评估，不是三个不同参数点。', '',
              '### 候选配置与选择依据', '',
              '| 方法 | 候选 | contextWindow | maxTokens | 已评分项通过数 / 有效项 | 缺失 | 完整三题、可入选 | 最终入选 |',
              '|---|---:|---:|---:|---:|---:|---|---|']
    for method, s in data.items():
        for c in s['candidates']:
            lines.append(f"| {method} | {c['candidate']} | {c['config']['contextWindow']} | {c['config']['maxTokens']} | {c['passes']} / {c['scored']} | {c['missing']} | {'是' if c['eligible'] else '否'} | {'是' if c['selected'] else '否'} |")
    lines += ['', '仅完整完成三道验证题的候选可入选；排序按严格通过数、平均 reward、较低费用、较早候选。Random 候选 2 虽通过一题，但另有一题缺失，因此不具备入选资格；Multifidelity 的未晋级候选不能把未评估的任务当作失败。', '',
              '### 搜索曲线', '', '![验证阶段搜索曲线](validation_search_curves.png)', '',
              '左图横轴为累计搜索记账费用（USD），纵轴为最佳验证通过率；仅在候选三题均有有效评分后更新，之前留空。右图辅助展示各槽位的累计费用和未归因区间。额外恢复启动的记录费用在本轮均为 0；这仅表示未观察到费用差额，不证明免费。两图均不包含最终测试。', '',
              '现有记录不足以做可靠的单参数因果敏感性或消融结论：Bayesian 重复同一配置，各候选任务覆盖也不完全相同。此处整理配置观察结果，不将其称为已完成消融实验。']
    return data, lines
