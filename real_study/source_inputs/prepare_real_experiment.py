"""Offline inventory and evidence audit; never launches agents or calls APIs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit_result(path):
    data = read_json(path)
    agent = data.get("agent_result") or {}
    trajectory = data.get("trajectory_summary") or {}
    record = {
        "result_path": str(path.resolve()),
        "task_name": data.get("task_name"),
        "agent": data.get("agent"),
        "model": data.get("model"),
        "reported_rewards": data.get("rewards"),
        "has_error": bool(data.get("error")),
        "error_category": data.get("error_category"),
        "has_verifier_error": bool(data.get("verifier_error")),
        "tool_calls": agent.get("n_tool_calls"),
        "steps": trajectory.get("steps"),
        "usage_source": agent.get("usage_source"),
        "reported_cost_usd": agent.get("cost_usd"),
        "cost_verified": False,
        "cost_note": "Provider usage is not reconciled; missing telemetry is not zero cost.",
        "pytest_counts": None,
        "ctrf_counts": None,
        "scoring_consistent": None,
        "scoring_unit_note": None,
        "strict_task_pass": None,
    }
    verifier = path.parent / "verifier"
    output = verifier / "pytest_output.txt"
    if output.exists():
        content = output.read_text(encoding="utf-8", errors="replace")
        summaries = re.findall(r"(?m)^=+ (.+?) in [0-9.]+s.*?=+\s*$", content)
        if summaries:
            counts = {key: int(value) for value, key in re.findall(
                r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)", summaries[-1]
            )}
            record["pytest_counts"] = counts
            record["strict_task_pass"] = (
                counts.get("passed", 0) > 0
                and not any(counts.get(k, 0) for k in ("failed", "error", "errors", "skipped", "xfailed", "xpassed"))
                and not record["has_error"] and not record["has_verifier_error"]
            )
    ctrf = verifier / "ctrf.json"
    if ctrf.exists():
        summary = read_json(ctrf).get("results", {}).get("summary", {})
        record["ctrf_counts"] = {key: summary.get(key) for key in ("tests", "passed", "failed", "skipped")}
        counts = record["pytest_counts"]
        if counts is not None:
            if summary.get("tests") == sum(counts.values()):
                record["scoring_consistent"] = (
                    summary.get("passed") == counts.get("passed", 0)
                    and summary.get("failed") == counts.get("failed", 0)
                )
            else:
                record["scoring_unit_note"] = (
                    "CTRF entries and pytest items have different counting units; "
                    "different totals alone do not demonstrate a scoring error."
                )
    record["result_sha256"] = digest(path)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.home() / "pe6203-linux/skillsbench")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not (repo / "tasks").is_dir():
        raise SystemExit("SkillsBench tasks directory not found: " + str(repo))
    output = repo.parent / "pe6203-experiment"
    output.mkdir(exist_ok=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    inventory = []
    for task in sorted((repo / "tasks").iterdir()):
        definition = next((task / name for name in ("task.md", "task.toml") if (task / name).is_file()), None)
        if not task.is_dir() or definition is None:
            continue
        inventory.append({"name": task.name, "definition_sha256": digest(definition),
                          "development_only": task.name == "dialogue-parser"})
    job = repo / "jobs/pi-fixed-20261028-142245/2026-10-28__14-22-48"
    results = [audit_result(p) for p in sorted(job.rglob("result.json"))] if job.exists() else []
    patch = {}
    spec = importlib.util.find_spec("benchflow")
    if spec and spec.origin:
        registry = Path(spec.origin).parent / "agents/registry.py"
        if registry.exists():
            source = registry.read_text(encoding="utf-8")
            patch = {"registry_sha256": digest(registry),
                     "pi_0810_pinned": "@earendil-works/pi-coding-agent@0.81.0" in source,
                     "acp_0034_pinned": "pi-acp@0.0.34" in source}
    report = {"phase": "preparing_real_evaluator", "repo": str(repo),
              "benchmark_commit": commit, "installation": patch,
              "total_budget_usd": 10, "budget_remaining_usd": None,
              "task_inventory": inventory, "development_results": results,
              "formal_split_created": False, "paid_runs_started_by_this_script": 0}
    report_path = output / "preflight.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已保存：", report_path)
    print("任务数量：", len(inventory))
    print("Pi/ACP 固定版本：", patch.get("pi_0810_pinned"), patch.get("acp_0034_pinned"))
    for result in results:
        print("开发任务：", result["task_name"])
        print("pytest：", result["pytest_counts"], "CTRF：", result["ctrf_counts"])
        print("评分统计一致：", result["scoring_consistent"])
        print("严格整题通过：", result["strict_task_pass"])
    print("没有启动付费评测；尚未创建正式验证/测试划分。")


if __name__ == "__main__":
    main()
