"""Offline held-out summary from final ledgers; no model or account requests."""
import hashlib
import json
from pathlib import Path
import run_search as runner
import validation_summary

ROOT = Path(__file__).resolve().parent
METHODS = ('default', 'random', 'bayesian', 'multifidelity')


def main():
    protocol_path = ROOT / 'final_test_protocol.json'
    protocol = runner.read(protocol_path)
    fingerprint = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    methods, evidence = {}, {}
    for method in METHODS:
        path = ROOT / f'test_{method}_state.json'
        state = runner.read(path)
        if state['frozen_protocol_sha256'] != fingerprint:
            raise RuntimeError('Frozen protocol mismatch: ' + method)
        rows = state['records']
        if len(rows) != len(protocol['test']) or any(not runner.resolved(r) for r in rows):
            raise RuntimeError('Incomplete or unresolved test ledger: ' + method)
        if [(r['candidate'], r['task_index'], r['task']) for r in rows] != [
                (0, i, t['name']) for i, t in enumerate(protocol['test'])]:
            raise RuntimeError('Duplicate or incorrect test slots: ' + method)
        if state['configs'] != [protocol['selections'][method]['config']]:
            raise RuntimeError('Configuration changed: ' + method)
        scored = [r for r in rows if r['status'] == 'complete']
        for row in scored:
            if not isinstance(row.get('reward'), (int, float)) or row.get('cost_usd') is None:
                raise RuntimeError('Missing score/cost: ' + method)
        methods[method] = {
            'config': state['configs'][0], 'slots': len(rows), 'scored': len(scored),
            'missing': len(rows) - len(scored),
            'passes': sum(r['strict_pass'] is True for r in scored),
            'pass_rate_scored_only': sum(r['strict_pass'] is True for r in scored) / len(scored) if scored else None,
            'scored_observed_usd': sum(r['cost_usd'] for r in scored),
            'unattributed_failure_interval_usd': sum(r.get('unattributed_interval_usd', 0) for r in rows),
            'budget_accounted_usd': runner.accounted_cost(state),
            'tasks': [{k: r.get(k) for k in ('task', 'status', 'reward', 'strict_pass', 'cost_usd',
                       'unattributed_interval_usd', 'error', 'missing_reason', 'result_paths')} for r in rows]}
        evidence[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = {'scope': 'Held-out tests only; excludes search, probes, and environment preparation.',
               'protocol_sha256': fingerprint, 'source_sha256': evidence, 'methods': methods,
               'slots': sum(m['slots'] for m in methods.values()),
               'scored': sum(m['scored'] for m in methods.values()),
               'missing': sum(m['missing'] for m in methods.values()),
               'passes': sum(m['passes'] for m in methods.values()),
               'test_budget_accounted_usd': sum(m['budget_accounted_usd'] for m in methods.values())}
    validation, validation_lines = validation_summary.build(ROOT, protocol)
    summary['validation'] = validation
    summary['validation_budget_accounted_usd'] = sum(s['budget_accounted_usd'] for s in validation.values())
    summary['search_and_test_accounted_usd'] = summary['validation_budget_accounted_usd'] + summary['test_budget_accounted_usd']
    summary['scope'] = 'Validation search and held-out test accounting; excludes earlier baseline, probes, and environment preparation.'
    lines = ['# 最终测试结果汇总', '',
             f"共 {summary['slots']} 个测试槽位，{summary['scored']} 项有效评分，{summary['missing']} 项缺失，{summary['passes']} 项通过。", '',
             '| 方法 | 有效评分 | 通过 | 缺失 | 有效评分内通过率 | 已评分任务费用 USD | 失败未归因区间 USD |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name, m in methods.items():
        rate = f"{m['pass_rate_scored_only']:.1%}" if m['scored'] else 'N/A'
        lines.append(f"| {name} | {m['scored']} | {m['passes']} | {m['missing']} | {rate} | {m['scored_observed_usd']:.8f} | {m['unattributed_failure_interval_usd']:.8f} |")
    lines += ['', f"测试预算记账总额：USD {summary['test_budget_accounted_usd']:.8f}。仅为测试阶段，不是整个项目总费用。", '',
              '## 配置、验证与最终测试总表', '',
              '| 方法 | 冻结配置 contextWindow / maxTokens | 入选候选验证通过 | 最终测试通过 / 有效项 | 测试缺失 | 搜索记账 USD | 测试记账 USD | 搜索加测试 USD |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for name, m in methods.items():
        config = m['config']
        label = f"{config['contextWindow']} / {config['maxTokens']}" if config else '默认，不覆盖参数'
        v = validation.get(name)
        vpass = f"{v['selected']['validation_pass_rate'] * 3:.0f} / 3" if v else ('1 / 3（历史真实基线）' if (ROOT/'validation_default_summary.json').exists() else '未纳入本次整理')
        search_cost = f"{v['budget_accounted_usd']:.8f}" if v else '—'
        combined = f"{v['budget_accounted_usd'] + m['budget_accounted_usd']:.8f}" if v else '—'
        lines.append(f"| {name} | {label} | {vpass} | {m['passes']} / {m['scored']} | {m['missing']} | {search_cost} | {m['budget_accounted_usd']:.8f} | {combined} |")
    lines += ['', f"三种优化器搜索记账合计 USD {summary['validation_budget_accounted_usd']:.8f}；加上四种方法测试，已整理范围合计 USD {summary['search_and_test_accounted_usd']:.8f}。不包含早期 Default 基线、诊断探针和环境准备费用，不能称为整个项目总花费。", '',
              '验证得分与测试得分分别报告，不合并计算通过率。Default 的搜索费用未适用，使用 —，不把未整理数据填成 0。']
    lines += validation_lines
    baseline_path = ROOT / 'validation_default_summary.json'
    if baseline_path.exists():
        baseline = runner.read(baseline_path)
        for row in baseline['rows']:
            if hashlib.sha256((ROOT / 'validation_default_evidence' / row['source_file']).read_bytes()).hexdigest() != row['source_sha256']:
                raise RuntimeError('Default validation evidence changed.')
        summary['earlier_default_validation'] = baseline
        lines += ['', '## 补充核对的真实 Default 验证基线', '',
            '此前未纳入整理的三条真实基线记录现已找回并复制到 validation_default_evidence/；不是 demo 合成数据。它们早于优化器搜索和安装加固，原始 Linux jobs 尚未重新读取，以下来自保存的结果摘要。', '',
            '| 验证任务 | Default reward | 入选 Bayesian 候选 reward | 观察对比 |', '|---|---:|---:|---|']
        selected_id = validation['bayesian']['selected']['candidate']
        selected_rows = [r for r in runner.read(ROOT/'bayesian_state.json')['records'] if r['candidate'] == selected_id]
        for row in baseline['rows']:
            other = next(r for r in selected_rows if r['task'] == row['task'])
            note = '均失败' if not row['strict_pass'] and not other['strict_pass'] else ('Default 成功、Bayesian 失败' if row['strict_pass'] else 'Default 失败、Bayesian 成功')
            lines.append(f"| {row['task']} | {row['reward']} | {other['reward']} | {note} |")
        lines += ['', f"Default 验证基线为 {baseline['passes']}/{baseline['tasks']}，即 {baseline['pass_rate']:.1%}；历史基线观察费用 USD {baseline['observed_accounted_usd']:.8f}，单列而非当作 HPO 搜索费用。验证到包含补测的测试差距为 −33.3 个百分点。", '',
            '两种成败相反的案例均来自验证集，不冒充最终测试案例；这是事后挑选的描述性比较，受随机性和环境差异影响，不足以证明配置引发该差异。未晋级/不完整候选和 demo 合成数据不用于补齐案例。']
    lines += ['', '## 参数敏感性与泛化差距', '',
              '[参数敏感性分析](parameter_sensitivity.md)使用现有验证记录，形成 6 组固定另一参数的对比；属于事后探索，尚不能可靠排名参数重要性。', '',
              '| 方法 | 入选候选验证通过率 | 测试有效项内通过率 | 测试减验证 | 限制 |',
              '|---|---:|---:|---:|---|']
    for name, v in validation.items():
        test = methods[name]
        vr = v['selected']['validation_pass_rate']
        tr = test['pass_rate_scored_only']
        limitation = f"测试 {test['missing']} 项缺失，仅按有效项计算" if test['missing'] else '仅三个测试任务'
        lines.append(f"| {name} | {vr:.1%} | {tr:.1%} | {(tr-vr)*100:+.1f} 个百分点 | {limitation} |")
    lines += ['', '上述差距是不同验证/测试任务集上的描述性比较。Bayesian 原始测试只有两项有效评分，不能把该差距当作无偏的完整测试估计或过拟合的因果证据。历史 Default 基线和包含补测的差距在独立章节说明。']
    supplement_dir = ROOT / 'supplementary_test'
    supplement_paths = [supplement_dir / f'{m}_state.json' for m in ('default', 'bayesian')]
    if all(p.exists() for p in supplement_paths):
        amendment_path = supplement_dir / 'amendment.json'
        amendment = runner.read(amendment_path)
        for name, expected in amendment['original_sha256'].items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError('Original evidence differs from supplement amendment: ' + name)
        supplements = {}
        for path in supplement_paths:
            state = runner.read(path)
            if state['amendment_sha256'] != hashlib.sha256(amendment_path.read_bytes()).hexdigest() or len(state['records']) != 1:
                raise RuntimeError('Invalid supplementary ledger: ' + str(path))
            row = state['records'][0]
            if row['status'] not in ('complete', 'missing') or row.get('cost_usd') is None:
                raise RuntimeError('Supplementary outcome or billing unresolved.')
            if row['status'] == 'complete' and row['raw_result']['rewards']['reward'] != row['reward']:
                raise RuntimeError('Supplement reward differs from saved raw result.')
            supplements[state['method']] = {k: row.get(k) for k in ('task','status','reward','strict_pass','cost_usd','result_paths','result_sha256')}
        extra = sum(r['cost_usd'] for r in supplements.values())
        completed = {}
        for name, method in methods.items():
            extra_row = supplements.get(name)
            scored = method['scored'] + int(extra_row is not None and extra_row['status'] == 'complete')
            passed = method['passes'] + int(extra_row is not None and extra_row.get('strict_pass') is True)
            completed[name] = dict(scored=scored, passes=passed, missing=method['slots']-scored,
                pass_rate=passed/scored if scored == method['slots'] else None,
                test_accounted_usd=method['budget_accounted_usd'] + (extra_row['cost_usd'] if extra_row else 0))
        summary['supplementary'] = dict(attempts=supplements, completed_estimates=completed,
            additional_accounted_usd=extra,
            primary_plus_supplement_test_usd=summary['test_budget_accounted_usd']+extra,
            search_primary_and_supplement_usd=summary['search_and_test_accounted_usd']+extra)
        lines += ['', '## 协议修订后的补充测试', '',
            '以下为观察原始失败后、依照 supplementary_test/amendment.json 各补一次的结果。原始主表和两项缺失记录保留，不覆盖、不取多次尝试的最高分。配置、任务和时限未改变。', '',
            '| 方法 | 补测任务 | 补测状态 | 补测 reward | 新增费用 USD |', '|---|---|---|---:|---:|']
        for name, r in supplements.items():
            lines.append(f"| {name} | {r['task']} | {r['status']} | {r['reward']} | {r['cost_usd']:.8f} |")
        lines += ['', '### 包含补测的三题结果', '',
            '| 方法 | 有效评分 | 通过 | 仍缺失 | supplemented pass@1 | 原始加补测执行记账 USD |',
            '|---|---:|---:|---:|---:|---:|']
        for name, m in completed.items():
            rate = f"{m['pass_rate']:.1%}" if m['pass_rate'] is not None else '未确定'
            lines.append(f"| {name} | {m['scored']} | {m['passes']} | {m['missing']} | {rate} | {m['test_accounted_usd']:.8f} |")
        lines += ['', f"新增补测记账 USD {extra:.8f}；原始测试加补测合计 USD {summary['supplementary']['primary_plus_supplement_test_usd']:.8f}；搜索、原始测试及补测合计 USD {summary['supplementary']['search_primary_and_supplement_usd']:.8f}。该范围仍不包含早期基线、诊断和环境准备。", '',
            'Default 与 Bayesian 获得额外尝试，应披露公平性限制。补测后的 Bayesian 三题通过率为 0%，较入选候选验证通过率低 33.3 个百分点；这仍是小样本、不同任务集的描述性差距，不能单独证明过拟合。']
        if (ROOT / 'final_test_evidence/supplementary_manifest.json').exists():
            lines += ['', '补测日志已归档并核对结果 SHA-256。两次 Scala 源文件均能编译，但测试编译出现 21 个符号解析错误；未进入单元测试执行。代码质量启发式分数 88%/96% 不等于官方 reward。详见[失败分析](final_test_failure_analysis.md)及 final_test_evidence/supplementary_manifest.json。']
    lines += ['', '## 每项最终测试', '', '| 方法 | 任务 | 状态 | 得分 |', '|---|---|---|---:|']
    for name, m in methods.items():
        for r in m['tasks']:
            reward = '缺失' if r['reward'] is None else str(r['reward'])
            lines.append(f"| {name} | {r['task']} | {r['status']} | {reward} |")
    lines += ['', '## 可用于报告的结论与限制', '',
              '- 当前测试未观察到任何方法通过任务，不能据此声称某种优化方法优于其他方法。',
              '- 12 个槽位来自 4 种方法各评估相同的 3 个任务，并非 12 道独立题目。样本很小。',
              '- Default 的构建失败和 Bayesian 的无评分命令超时均为缺失，不能填成 0 分。',
              '- Random 首题达到固定 600 秒模型时限，评分器给出 0 分；保留超时证据，不重跑。',
              '- Random 与 Multifidelity 最终选择了相同配置；两者之间没有形成不同参数配置的比较。',
              '- 费用来自专用 Key 的观察差额，受延迟记账影响；失败区间单列，不能解释为精确单任务费用。',
              '- 原始测试日志已归档并核对 12 条结果；[失败分析](final_test_failure_analysis.md)及 final_test_evidence/ 保留编译、公式、结构断言证据。没有重新执行评分器。',
              '- 失败分析：四组 Excel 均未通过公式及计算检查；四组 Three.js 均有结构或网格问题；两个有评分的 Scala 输出存在编译或测试接口错误，另外两个 Scala 槽位缺失。',
              '- 验证配置、预算、费用横轴的 incumbent 曲线及探索性参数敏感性已整理；样本限制使参数重要性仍不能可靠判定。作业要求敏感性或消融方法，不要求两者分别完成。此项目前仅部分支撑要求。',
              '- 两种方法各有一次额外恢复启动，预算比较并非完全一致；相同上限不要求相同实际费用，但额外启动的待遇差异需要披露。两个方向的失败对比已由历史真实 Default 验证基线提供，不能称为 held-out 对比或因果证据。',
              '- 测试结果不用于重新选参。任何新增实验应另立协议并与本轮结果分开。', '']
    (ROOT / 'final_test_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'final_test_summary.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('methods', 'source_sha256', 'validation')}, indent=2))


if __name__ == '__main__':
    main()
