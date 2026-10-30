# PE6203 Project 3 — Low-code HPO Starter

**Status: working educational PROTOTYPE, NOT a completed official benchmark submission.**

This ZIP covers configuration generation, Default/Random/Bayesian/our two-stage HPO, seed control, synthetic task evaluation, cost accounting, raw CSV/JSON exports, and an incumbent curve.

## 1. Windows / VS Code quick start

Install Python 3.10+ (3.11 recommended). Open this folder in VS Code, open Terminal:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m src.experiment
```

For macOS/Linux replace activation with `source .venv/bin/activate`.

Outputs: `results/trials.csv`, `results/summary.json`, `results/incumbent.png`.

All these outputs are **SYNTHETIC** when `mode: demo`. Never represent them as Pi/SkillsBench performance.

## 2. What still needs to be completed for the course

1. Select ONE course-approved harness and benchmark (candidate: Pi + SkillsBench 1.1). Verify available versions, licenses, installation and exact supported parameter interfaces. Pi is a JavaScript/TypeScript program; Python can orchestrate its CLI. Pi documentation: https://pi.dev/docs/latest/cli .
2. Replace `official_task` in `src/harness_adapter.py`: invoke official benchmark runner with fixed model/settings/tasks and proper timeout handling, then read official verifier pass/fail and **actual** price/token data. Keep benchmark task labels unseen during selection. Never hard-code solved task IDs.
3. Change `configs/config.yaml` to `mode: real`, replace abstract steps/retries/context with *verified* exposed settings of the selected harness (the current demo settings are intentionally illustrative). Version-pin the repository and exact commands.
4. Create an official reproducible validation/test split. The two sets must not overlap. Only run held-out tests after selecting configurations. Store full per-task raw logs, configs, exceptions, and versions.
5. Use equal evaluation budgets and comparable information for random/Bayesian/own methods. Current demo equalizes maximum **task evaluations**; full course analysis must also report cumulative USD search cost. The Default row is a reference, not equal-budget optimizer.
6. Conduct parameter sensitivity/ablation and failure-mode analysis (cases where tuned config fails but default passes and vice versa). This is not yet implemented.
7. Check the independent-project scope and compute/API budget with instructor before committing to many official experiments.

## 3. Methods

- **Default**: midpoint configuration, no search.
- **Random**: Optuna RandomSampler.
- **Bayesian**: Optuna TPESampler (Bayesian-style sequential search).
- **Our method**: two-stage budget-aware screening. Screening on 25% of validation tasks, then fuller evaluation of promising configurations. Holds out test tasks; records costs. This is a starter design, not a claim of novelty or superiority.

## 4. Caveats

- The sample synthetic task generator only demonstrates workflow. It does not simulate any actual agent or official evaluation.
- This scaffold does not install Pi/SkillsBench or make API calls. No API charges in demo mode.
- Cost-aware strategy's screening score uses a small illustrative penalty; tune on validation only, and predeclare its values and evaluation budget in your final protocol.
- Report actual evaluation runs; include failures and limitations rather than hiding poor results.
