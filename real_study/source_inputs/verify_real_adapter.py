"""Offline check of the installed BenchFlow-to-Pi configuration bridge.

No model calls, Docker operations, installations, credentials, or source edits.
Run with the same Python interpreter that owns the benchflow installation.
"""
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import runpy
from unittest.mock import patch


def check_launcher(path):
    module = runpy.run_path(str(path), run_name="adapter_audit")
    class MemoryPath:
        """Keep synthetic Pi config entirely in memory."""
        files = {}

        def __init__(self, name="audit-home"):
            self.name = name

        @classmethod
        def home(cls):
            return cls()

        def __truediv__(self, child):
            return type(self)(self.name + "/" + child)

        def mkdir(self, **kwargs):
            pass

        def exists(self):
            return self.name in self.files

        def read_text(self):
            return self.files[self.name]

        def write_text(self, text):
            self.files[self.name] = text

    module["setup_provider"].__globals__["Path"] = MemoryPath
    cases = [(128000, 16384), (64000, 4096), (96000, 8192)]
    results = []
    for context, output in cases:
        # Synthetic credentials only; do not inherit the real terminal key.
        env = {
            "BENCHFLOW_PROVIDER_PROTOCOL": "openai-completions",
            "BENCHFLOW_PROVIDER_BASE_URL": "https://example.invalid/v1",
            "BENCHFLOW_PROVIDER_API_KEY": "offline-test-only",
            "BENCHFLOW_PROVIDER_NAME": "offline-test",
            "BENCHFLOW_PROVIDER_MODEL": "qwen/qwen3-coder",
            "BENCHFLOW_PROVIDER_MODELS": json.dumps([{
                "id": "qwen/qwen3-coder", "contextWindow": context,
                "maxTokens": output, "reasoning": False,
            }]),
        }
        MemoryPath.files.clear()
        with patch.dict("os.environ", env, clear=True):
            module["setup_provider"]()
        data = json.loads(MemoryPath.files["audit-home/.pi/agent/models.json"])
        model = data["providers"]["offline-test"]["models"][0]
        results.append({"requested_context": context, "requested_output": output,
                        "config_context": model["contextWindow"], "config_output": model["maxTokens"],
                        "matches": model["contextWindow"] == context and model["maxTokens"] == output})
    return results


def main():
    spec = importlib.util.find_spec("benchflow")
    if not spec or not spec.origin:
        raise SystemExit("Use ~/.local/share/uv/tools/benchflow/bin/python to run this file.")
    root = Path(spec.origin).parent
    launcher = root / "agents/pi_acp_launcher.py"
    registry = root / "agents/registry.py"
    version = importlib.metadata.version("benchflow")
    registry_text = registry.read_text(encoding="utf-8")
    checks = check_launcher(launcher)
    pinned = ("@earendil-works/pi-coding-agent@0.81.0" in registry_text
              and "pi-acp@0.0.34" in registry_text)
    report = {
        "phase": "offline_bridge_check", "paid_evaluations_started": 0,
        "benchflow_version": version, "pi_install_versions_pinned": pinned,
        "launcher_sha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
        "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
        "configuration_bridge_checks": checks,
        "bridge_ready": version == "0.6.3" and pinned and all(c["matches"] for c in checks),
        "provider_request_effect_verified": False,
        "note": "Configuration transport only. Verify the pinned Pi request behavior before HPO; this is not benchmark performance evidence.",
    }
    out = Path(__file__).resolve().with_name("real_adapter_check.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("BenchFlow:", version)
    print("Pinned Pi/ACP:", pinned)
    print("Configuration bridge ready:", report["bridge_ready"])
    print("Paid tasks started: 0")
    print("Report:", out)


if __name__ == "__main__":
    main()
