"""Create a reproducible task split from existing inventory, without executing tasks."""
import hashlib
import json
from pathlib import Path


def main():
    output = Path(__file__).resolve().parent
    evidence = json.loads((output / "preflight.json").read_text(encoding="utf-8"))
    seed = "PE6203-P3-20261028-v1"
    eligible = [t for t in evidence["task_inventory"] if not t["development_only"]]
    ordered = sorted(eligible, key=lambda t: hashlib.sha256((seed + ":" + t["name"]).encode()).hexdigest())
    validation, test = ordered[::2], ordered[1::2]
    assert not ({t["name"] for t in validation} & {t["name"] for t in test})
    assert len(validation) + len(test) == len(eligible)
    manifest = {
        "status": "partition_only_not_a_run_schedule",
        "benchmark_commit": evidence["benchmark_commit"],
        "seed": seed,
        "method": "SHA256(seed:task_name) ascending; alternating validation/test",
        "development_excluded": [t["name"] for t in evidence["task_inventory"] if t["development_only"]],
        "validation": validation,
        "test": test,
        "rules": [
            "Do not use held-out test results to choose parameters, tasks, prompts or stopping rules.",
            "Partitioning does not authorize running all tasks; declare an affordable subset before runs.",
            "Audit runtime requirements and parameter effects before selecting the pilot subset.",
            "Preserve benchmark rewards; report task pass@1 separately from partial rewards.",
            "Missing token or cost telemetry is unknown, never zero.",
            "Reconcile prior provider spending before allocating the remaining total USD 10 budget."
        ],
        "paid_calls": 0,
    }
    target = output / "split_manifest.json"
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != encoded:
        raise SystemExit("Existing split differs; refusing to overwrite it.")
    target.write_text(encoded, encoding="utf-8")
    print(f"Saved split: validation={len(validation)}, test={len(test)}; paid calls=0")


if __name__ == "__main__":
    main()
