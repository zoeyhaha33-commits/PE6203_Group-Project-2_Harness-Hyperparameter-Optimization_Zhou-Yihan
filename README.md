# PE6203 Group Project 2: Harness Hyperparameter Optimization

Zhou Yihan

This submission contains experiment code, configurations, reports, presentation, and selected evidence for hyperparameter optimization of Pi on SkillsBench.

## Read the results

- [Final test summary](real_study/final_test_summary.md)
- [Failure analysis](real_study/final_test_failure_analysis.md)
- [Parameter sensitivity](real_study/parameter_sensitivity.md)
- [Presentation](real_study/presentation/output/PE6203_HPO_Presentation_Expanded_v2.pptx)
- [Speaker notes](real_study/presentation/output/Expanded_Speaker_Notes_and_Timing.md)
- [Validation curves](real_study/validation_search_curves.png)

## Contents

`real_study/` contains the real experiment scripts, frozen protocols, final search/test states, structured verifier evidence, and reporting scripts. `source_inputs/` preserves the earlier study plan and split configuration used by the runners. `PE6203_P3_Starter/` is the original educational scaffold; its demo results are synthetic and must not be interpreted as real benchmark performance. Historical Project 3 labels are retained in original artifacts.

The Markdown analyses above are the included reports. `build_report_draft.py` is a report-generation script; no generated Word report was present in the source directory.

## Benchmark dependency

The unmodified third-party SkillsBench checkout and its Python virtual environment are excluded. Obtain the exact source separately:

```sh
git clone https://github.com/benchflow-ai/skillsbench.git skillsbench
git -C skillsbench checkout b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af
```

Study settings and versions are recorded in `real_study/protocol.json`, `final_test_protocol.json`, `bayesian_environment.json`, and `pre_optuna_constraints.txt`. The fixed harness versions are Pi 0.81.0 and pi-acp 0.0.34. Follow the benchmark's own installation instructions and license.

## Running the code

For the synthetic scaffold, follow `PE6203_P3_Starter/README.md`. Real experiments require Docker/Linux, the benchmark dependencies, and locally configured provider credentials. Never commit credentials. Review the runner arguments before execution; paid evaluations require explicit execution flags.

The search runner defaults to the included `real_study/source_inputs` directory; `PE6203_SOURCE_DIR` overrides it. Some historical helper scripts and stored evidence retain machine-specific paths. Adapt those paths for a new environment; archived run states are evidence, not a clean rerun directory. Preserve them before launching any new evaluations. This submission does not claim a fresh end-to-end reproduction on another machine.

## Packaging

Virtual environments, caches, temporary slide renders, historical backup snapshots, raw compressed logs, and provider billing exports are excluded. Final JSON states, protocols, structured verifier evidence, analysis documents, and presentation output are retained. Full raw logs remain in the author's local workspace.
