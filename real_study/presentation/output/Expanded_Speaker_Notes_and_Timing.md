# 1. Harness hyperparameter optimization

Target: 20 seconds

Our project studies hyperparameter optimization over a fixed PI Agent harness. We compare a two-stage multi-fidelity method with Default, Random search and Bayesian optimization. This pilot did not produce a held-out performance gain; we explain the method, evidence and lessons.

# 2. Research problem and study design

Target: 35 seconds

The project treats harness improvement as configuration search. Our question is whether a small supported parameter surface improves success within a declared budget, and whether that improvement survives held-out testing. We separate the one-time search expense from the runtime cost of using the selected configuration. The contribution is a complete empirical workflow, including a student-developed multi-fidelity allocation strategy. The experiment is deliberately small, and we evaluate the claim with verifier outcomes rather than subjective output quality.

# 3. Fixed execution stack and reproducible task split

Target: 40 seconds

The fixed stack is PI 0.81.0 with pi-acp 0.0.34, BenchFlow 0.6.3 and Qwen3 Coder through OpenRouter. Runs use Docker, no skills, a single-shot loop and concurrency one. Validation uses financial modeling, JAX and travel planning; testing uses Scala translation, reserves at risk and Three.js parsing. Commit and task-definition fingerprints are recorded. Four methods on the same three test tasks produce twelve primary slots, not twelve independent questions. The small split is a major limitation.

# 4. Exposed parameters and configuration selection

Target: 40 seconds

The configuration space has three contextWindow values and three maxTokens values. These are passed through BenchFlow provider-model metadata to PI. Context controls the configured context budget and maxTokens the generation limit; this is not a claim about the model vendor’s maximum capability. Only candidates with three valid validation outcomes are eligible. Selection ranks strict passes, then mean official reward, then lower observed candidate cost, then candidate index. Default passes no overrides. Keeping the eligibility rule matters because a Random candidate with one success has another missing result.

# 5. Comparison methods and declared budgets

Target: 40 seconds

Default is untuned. Random samples three unique configurations and evaluates three tasks each. Bayesian uses standard Optuna TPE with one startup trial and three candidate records; duplicates are allowed and all three records happen to be identical here. Our method allocates five screening tasks and four continuations. Actual search launches differ because Random and multi-fidelity each used one additional recovery attempt. Equal budget ceilings do not require equal actual spending, but asymmetric extra opportunities are a fairness limitation. We disclose them instead of claiming completely equal realized attempts.

# 6. Developed method: two-stage multi-fidelity search

Target: 60 seconds

The developed method samples five unique configurations and tests each on financial-modeling-qa. It promotes two using the declared ranking and evaluates JAX and travel only for those two, reusing the screen. That is five plus four slots. In this run candidates one and zero are promoted, and zero is eventually selected because candidate one has a missing continuation outcome. All five screens score zero, so the screening signal cannot separate success and promotion depends on tie-breaking. This explains why the method’s intended allocation efficiency is not enough to establish performance or cost improvement.

# 7. Implementation and outcome accounting

Target: 35 seconds

The implementation is Python orchestration around the fixed BenchFlow and PI runtime. Configuration generation creates candidate records. The launcher persists a slot before a subprocess, runs the harness and retains the official raw verifier result. Dedicated-key usage snapshots are used for costs because token telemetry may be unavailable. Source task hashes and frozen selection hashes stop unnoticed changes. Missing outcomes, scored zeros and billing-pending states remain distinct. Installation hardening changed bounded download retries and checks, not the agent loop, but was introduced during validation and is disclosed.

# 8. Validation incumbent and configuration selection

Target: 60 seconds

The curve is plotted against cumulative observed search cost, with straight step segments. Bayesian obtains one success out of three at about ten cents, then retains it. Random’s eligible candidates remain at zero; its other candidate has a success but is incomplete, so it cannot be the incumbent. Multi-fidelity only completes an eligible candidate at the final slot; its incumbent is a single point at zero. Therefore the graph provides little evidence about early convergence for that method. Default has no search curve because it is untuned. The right-side selected settings explain the final evaluation.

# 9. Held-out performance and generalization

Target: 50 seconds

The original final test has ten valid zeros and two missing outcomes. An explicitly recorded later amendment permits one supplementary Scala launch each for the two missing Default and Bayesian slots. Both supplements finish with official zero and settled costs. We preserve the original results and separately present supplemented estimates. Every method has zero successes out of three after supplementation. Bayesian’s gap is minus thirty-three point three percentage points from the selected validation candidate. Default’s historical validation baseline also has one success, but predates the later installation wrapper, another comparison caveat.

# 10. Search cost versus selected-configuration runtime cost

Target: 45 seconds

The stacked chart separates one-time search from primary plus supplementary test execution. Search costs are approximately 0.2043 dollars for Random, 0.1416 for Bayesian and 0.3058 for multi-fidelity. Multi-fidelity is the most expensive here, affected by one costly screen. Total search plus test and supplement accounting is 0.991319 dollars. The old Default validation baseline is 0.14043120 dollars and excluded from that scope, as are probes and preparation. A stable usage difference is not a hard provider billing guarantee. With no solved test tasks, cost per solved task and an amortization break-even claim are unsupported.

# 11. Parameter sensitivity: matched validation observations

Target: 50 seconds

We retain the report’s exploratory sensitivity analysis rather than imply that a full ablation was performed. It uses twenty-five scored records and six matched comparisons. Increasing maxTokens from 4096 to 8192 at context 128k has the largest observed cost contrast, but the larger setting has only one run and no financial-task success. Larger context coincides with successes on JAX and travel, with unequal repeats and method/order confounding. The two large financial contrasts share one expensive run. We can report these observations, but cannot rank causal importance or estimate harmful interaction.

# 12. Validation reversals and held-out failure evidence

Target: 65 seconds

The report contains both requested directional examples on validation. Default fails JAX while selected Bayesian succeeds; Default succeeds travel while the selected Bayesian candidate fails. These are real historical baseline records, not synthetic demo data. Raw baseline Linux jobs have not been re-read, so we do not invent their behavioral causes. The held-out logs are available and show concrete faults: required Excel formulas are missing; Three.js instance structures or vertices are missing; Scala has source or test-compilation failures. For both supplements, source compilation succeeds but test compilation fails with twenty-one symbol-resolution errors. These problems explain valid zeros without equating heuristic quality scores with task success.

# 13. Interpretation, fairness and validity limits

Target: 35 seconds

Three threats are especially important. First, only three test tasks and sparse independent repetitions limit generalization. Second, the methods share declared caps, but two have extra recovery launches; observed cost differences alone are not the fairness issue. Third, failure-handling rules, installation hardening and the supplements were amended during the study. We preserve provenance and distinguish main from supplemental results. The Default/Bayesian validation reversals are descriptive, and sensitivity cannot identify causal effects. These are remaining evidence limitations, not issues that can be fixed by relabeling a chart.

# 14. Conclusions and lessons learned

Target: 25 seconds

We implemented a two-stage method and compared it with all three required references. No held-out improvement was observed. Screening quality matters because every candidate failed the proxy task. Future work should predeclare recovery rules and use repeated balanced validation to estimate parameter effects. The value of this pilot is a reproducible, cost-accounted record of what worked operationally and what did not improve task success.

# 15. Discussion and Q&A

Q&A / backup

Discuss the evidence limitations directly. A zero result is still reportable when verification and execution are auditable. The supplements were declared after observing two unscored failures, not used to retry scored zeros. The sensitivity results are exploratory due to time and replication limits. No optimizer superiority is claimed.

# 16. Backup: candidate history and final selection

Q&A / backup

The Random candidate with one success is ineligible because another task is missing. TPE selected candidate one despite proposing the same configuration in all three records. Multi-fidelity candidates two to four were screened but not continued, not counted as failures on unobserved tasks. Candidate one was promoted but missing a continuation; candidate zero was selected.

# 17. Backup: all six matched-parameter contrasts

Q&A / backup

Each pair compares the same task at a fixed other parameter. Two financial contrasts share the single expensive context128k/maxTokens8192 run. These rows should not be interpreted as independent repeated evidence of an interaction. No new factorial experiment was performed.

# 18. Backup: protocol amendment and evidence trail

Q&A / backup

The original twelve slots remain ten valid zeros and two missing outcomes. The supplementary amendment freezes original hashes and allows Default and Bayesian one extra Scala launch each without parameter or time-limit changes. Both score zero. Primary test accounting is 0.31901342 dollars and additional accounting is 0.02054630. Hash-checked archives and indexed verifier output support the final result. The earlier Default baseline adds separate cost but not optimizer-search expenditure. No synthetic demo artifacts are used as course evidence.
