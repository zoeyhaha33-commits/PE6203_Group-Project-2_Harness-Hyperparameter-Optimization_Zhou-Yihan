"""Run exactly one development task and reconcile current-key usage before/after."""
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request


def metadata(key):
    req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                 headers={"Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)["data"]


def main(model_metadata=None):
    shared = Path(__file__).resolve().parent
    repo = Path.home() / "pe6203-linux/skillsbench"
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key or key != os.environ.get("LITELLM_API_KEY", "").strip():
        raise SystemExit("Missing or inconsistent keys in this terminal; no run started.")
    if not (repo / "tasks/dialogue-parser/task.md").is_file():
        raise SystemExit("Development task not found; no run started.")
    bench = shutil.which("bench")
    if not bench:
        raise SystemExit("bench not found on PATH; no run started.")
    docker = subprocess.run(["docker", "info", "--format", "{{.OSType}}"],
                            capture_output=True, text=True)
    if docker.returncode or docker.stdout.strip() != "linux":
        raise SystemExit("Docker Linux engine unavailable in this terminal; no paid run started.")
    with (shared / "preflight.json").open(encoding="utf-8") as handle:
        expected = json.load(handle)["benchmark_commit"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if commit != expected:
        raise SystemExit("Benchmark commit changed; no run started.")
    before = metadata(key)
    if not isinstance(before.get("usage"), (int, float)):
        raise SystemExit("Provider usage missing; no run started.")
    if before["usage"] >= 9.5:
        raise SystemExit("Less than USD 0.50 admission reserve remains under the USD 10 allocation; no run started.")
    # A concurrent evaluation on this key would invalidate usage-delta accounting.
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    jobs = repo / "jobs" / ("cost-calibration-" + stamp)
    report_path = shared / ("calibration-" + stamp + ".json")
    command = [bench, "eval", "run", "--tasks-dir", "tasks/dialogue-parser",
               "--agent", "pi", "--model", "litellm/qwen/qwen3-coder",
               "--sandbox", "docker", "--skill-mode", "no-skill",
               "--loop-strategy", "single-shot", "--concurrency", "1",
               "--jobs-dir", str(jobs)]
    if model_metadata is not None:
        command += ["--agent-env", "BENCHFLOW_PROVIDER_MODELS=" + json.dumps([model_metadata], separators=(",", ":"))]
    report = {"phase": "development_cost_calibration", "benchmark_commit": commit,
              "jobs_dir": str(jobs), "key_usage_before_usd": before["usage"],
              "total_project_budget_usd": 10, "max_task_runs": 1,
              "formal_test": False, "status": "started"}
    report["model_metadata_override"] = model_metadata
    report["budget_note"] = "USD 0.50 admission reserve, not a hard per-task spending limit. Dedicated key and no concurrent requests required."

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    env = dict(os.environ, LITELLM_BASE_URL="https://openrouter.ai/api/v1")
    print("Running ONE development task. Do not use this API key elsewhere during the run.", flush=True)
    print("Report:", report_path, flush=True)
    # This launches a task, not a search loop. The benchmark retains its task timeout.
    try:
        report["returncode"] = subprocess.run(command, cwd=repo, env=env).returncode
    finally:
        report["status"] = "process_finished_or_interrupted"
        report["results"] = []
        for result_path in sorted(jobs.rglob("result.json")) if jobs.exists() else []:
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                agent = result.get("agent_result") or {}
                report["results"].append({"path": str(result_path), "rewards": result.get("rewards"),
                    "has_error": bool(result.get("error")), "error_category": result.get("error_category"),
                    "has_verifier_error": bool(result.get("verifier_error")),
                    "tool_calls": agent.get("n_tool_calls"), "telemetry_cost_usd": agent.get("cost_usd")})
            except (OSError, ValueError):
                report["results"].append({"path": str(result_path), "readable": False})
        save()
        snapshots = []
        for delay in (0, 10, 20):
            if delay:
                time.sleep(delay)
            try:
                current = metadata(key)
                snapshots.append({"checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                  "usage": current.get("usage")})
            except Exception as exc:
                snapshots.append({"query_error_type": type(exc).__name__})
        usages = [s["usage"] for s in snapshots if isinstance(s.get("usage"), (int, float))]
        report["usage_snapshots"] = snapshots
        report["observed_cost_delta_usd"] = max(usages) - before["usage"] if usages else None
        report["cost_note"] = "Observed key usage delta; assumes no other requests on this key. Billing can be delayed; zero delta is not confirmed free usage."
        save()
        print("Saved:", report_path)
        print("Observed cost delta (USD):", report["observed_cost_delta_usd"])
        print("Calibration finished. No additional task will be launched.")


if __name__ == "__main__":
    main()
