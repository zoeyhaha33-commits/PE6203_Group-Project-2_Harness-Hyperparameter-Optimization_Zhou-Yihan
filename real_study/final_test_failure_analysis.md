# 最终测试失败分析

证据来源：`final_test_logs.tar.gz` 中的原始 result.json 和 verifier 日志。已核对 12 条结果的任务名、有效评分与状态账本一致，以及已有审计记录的结果 SHA-256。一份便于阅读的证据副本和索引保存在 `final_test_evidence/`。这是离线分析，未调用模型、重跑测试或修改评分。

## 结果概况

四种方法各评估同样三个任务，共 12 个槽位；10 项有效评分均为 0，另外 2 项缺失。不能将缺失填成 0，也不能声称本轮证明某种方法更优。Random 和 Multifidelity 选中了同一配置，不能把它们解释为不同参数配置之间的比较。

## 1. reserves-at-risk-calc：四种方法均未满足公式和计算要求

四组日志均显示 4 failed、1 passed。通过的是 `test_no_errors_or_macros`；失败的是三个步骤的计算检查以及 `test_formulas_present`。

共同证据：Gold price 工作表 C–E 列被检测到的公式数为 0；Answer 工作表规定的公式单元格存在空值、常数或不符合预期的内容。Default 的 C4 为数值、C5 为字符串；Multifidelity 的 C13/C22/C24 为硬编码数值。即使存在部分计算结果，也不满足必须使用 Excel 公式的要求。

证据：`final_test_evidence/{default,random,bayesian,multifidelity}_2/test-stdout.txt`。

结论范围：日志支持“输出未满足指定单元格与公式要求”，不支持“仅调整 contextWindow 或 maxTokens 即可解决”。

## 2. threejs-structure-parser：四种方法均未通过结构和网格检查

四组日志均显示 2 failed、1 passed。输出目录存在检查通过，但部件网格与链接网格检查失败。

- Default：缺少多个 cabin_N 部件目录和链接 OBJ。
- Random：输出含统一的 cabin 目录，未满足各 cabin_N 实例目录的要求；链接 OBJ 列表也不匹配。
- Bayesian：部件目录使用 cabins 等名称，与期望实例目录不符；wheel_structure.obj 未解析出顶点。
- Multifidelity：缺少 cabin_N 部件目录；wheel_structure.obj 未解析出顶点。

证据：`final_test_evidence/{default,random,bayesian,multifidelity}_3/test-stdout.txt`。

日志中的 `Verifier exited with rc=1 but produced reward output` 在这些案例中伴随明确的断言失败和新生成的 reward=0。它不等于没有有效评分，也不表示任务通过。

## 3. python-scala-translation：分别记录编译失败、超时和缺失

| 方法 | 记录方式 | 原始证据 |
|---|---|---|
| Default | 缺失 | Docker 构建下载 JDK 失败，无 reward |
| Random | 有效评分 0，保留模型超时标记 | 600 秒模型时限；13 次工具调用；评分器 output.log 显示 Double 模式类型与 Number 不兼容，源代码编译失败，单元测试跳过 |
| Bayesian | 缺失 | Command timed out after 900 seconds；rewards 和 agent_timeout_info 均为空；不能由零工具/token 统计推断模型未启动或没有费用 |
| Multifidelity | 有效评分 0 | output.log 显示测试编译失败，包括找不到 TokenizerBuilder、maxLength、stripPunctuation 等符号，合计 21 个错误 |

证据：`final_test_evidence/*_1/result.json`，以及 `random_1/output.log`、`multifidelity_1/output.log`。

Random 与 Multifidelity 的 output.log 还出现代码质量启发式分数 23/25（92%），但该分数不是本实验的官方 reward。编译或测试未通过时，不得将 92% 当作任务通过率。

Bayesian 的 900 秒超时日志不足以单独确定根因；本轮保留为未评分命令超时，不据此声称是模型能力失败。

## 4. 协议修订后的两项补测

Default 与 Bayesian 的 Scala 补测均获得有效 reward=0，费用已结清。补测原始 result.json 的 SHA-256 已与各自账本核对一致，证据保存在 `final_test_evidence/supplement_default_1/`、`supplement_bayesian_1/`，索引为 `supplementary_manifest.json`。原始失败与缺失记录保留。

两份 verifier/output.log 均显示源文件 Compilation successful，但测试编译失败，共 21 个错误，包括无法解析 TokenType、Token、TokenContainer、UniversalTokenizer、TokenizerBuilder 等符号和命名参数。`Tests passed: 0/0` 表示没有成功进入单元测试执行，不能解释为已经执行并全部失败的 0/N 测试。

轨迹中能看到生成的 TokenType 等定义，却未检索到 `package tokenizer`。这与测试作用域或包集成不匹配的解释一致，但没有重新编译验证，不能据此宣称唯一根因或修改代码后必然通过。不能修改输出文件后重新评分并覆盖本轮结果。

Default 的启发式代码质量分数为 22/25（88%），Bayesian 为 24/25（96%）；它们均不是官方 reward，也不是任务通过率。包含补测后三题通过率四种方法均为 0%，不支持优化方法提升测试性能的结论。

## 报告下一步

补充核查找回了三个真实 Default 验证摘要，见 validation_default_evidence/ 和 validation_default_summary.json。JAX 题上 Default reward=0、实际入选的 Bayesian 候选 1 reward=1；旅行规划上 Default reward=1、该 Bayesian 候选 reward=0。两个方向的案例现可在验证阶段展示；它们不是 held-out 案例。历史基线 Linux 原始轨迹尚未重新读取，不能编造具体行为根因，也不能把随机差异归因于参数或证明有害交互。旧 demo 合成结果完全排除。

1. 使用 final_test_summary.md 的表格汇报测试得分、缺失数量和测试费用，明确只有 3 道独立任务。
2. 单独整理验证阶段的候选配置、搜索预算、累计费用和 incumbent 曲线；与 held-out 测试分开。
3. 用以上三类失败案例解释零分，而不是只报告总通过率。不得将代码质量分数或部分子测试通过率替换为官方得分。
4. 核对课程要求的参数敏感性、消融分析和交付格式。若需要额外实验，应另立协议，注明探索性质，不用已观察的测试结果重新选参并覆盖本轮。
5. 本分析不能证明评分器无缺陷；这里只核查原始日志和输出一致性，没有重新执行评分器或修复模型生成文件。
