# 补充测试协议修订

修订日期：2026 年 10 月 30 日。用户在查看原始结果和失败日志后，要求为两项未评分结果准备补测。该修订是事后修订，不冒充原始预注册规则。

机器可核对的协议为 amendment.json，已在任何补测模型请求之前通过离线预览冻结。它保存原始最终协议及四种方法测试账本的 SHA-256。原文件、原始缺失记录及报告主表均保留。

## 范围和停止规则

- 仅补 Default 与 Bayesian 的 python-scala-translation；各最多一次额外 wrapper 启动，不重测已有有效评分。
- Default 不覆盖参数；Bayesian 使用原冻结的 contextWindow=128000、maxTokens=4096。
- 模型、agent、task、验证器、资源及 600 秒模型时限保持原样。允许使用已成功准备的 Docker 镜像缓存，不修改任务 Dockerfile 或模型生成的文件。
- Default 原始失败证据是 Docker 构建期间 apt/JDK 下载失败。Bayesian 是 900 秒命令超时、空轨迹和无 reward，根因未确认；不将它描述为已证明的模型启动前故障。
- 不重新搜索、不依据补测结果选参，不取两次尝试中更好的分数。额外启动前即持久化已消耗槽位；再次无评分则补测也为缺失，不继续重试。
- 共享 search.lock，两个补测串行；前一个结果和费用未结清时禁止下一个启动。
- 费用单列且计入原始 USD 2 测试 admission 预算，保留 USD 0.20 准入预留和原有 Key 累计阈值，不重置预算。费用来自独占 Key 的观察区间，可能有延迟；观察到零不等于确认免费。

## 运行

在现有 WSL 环境使用原 benchflow Python 执行 run_supplementary_test.py。离线预览不需要 API Key，不调用模型：

```bash
~/.local/share/uv/tools/benchflow/bin/python "/mnt/d/NTU-EAI/EAI-T1/PE6203-/Group Assignment2/PE6203_P3_Starter/real_study/run_supplementary_test.py" --method default
```

将 `--execute --exclusive-key` 加到命令末尾执行一次补测。Default 输出 status 为 complete 或 missing 且已记录 cost_usd 后，才以 `--method bayesian --execute --exclusive-key` 执行第二项。

如果启动后费用核查中断，仅使用 `--reconcile-only --exclusive-key`；该参数不启动模型。若 returncode 未被记录，须先核查进程和 jobs 原始文件，不能直接重启。协议或原始账本指纹变化会阻止运行。

## 结果呈现

原始主表继续报告 12 个原始槽位、10 项有效评分、2 项缺失。另增“协议修订后的补充测试”表，展示原始失败、额外启动、补测得分、费用及证据路径。只有补测产生有效评分，才能给出清楚标注为 supplemented 的完整三题估计；原始结果仍同时呈现。两种方法获得额外尝试的公平性限制必须披露。不得宣称所有方法均只尝试一次。

完成状态：两项补测均已执行并结算。Default 和 Bayesian 均获得有效 reward=0；新增观察费用分别为 USD 0.01259510 和 USD 0.00795120。原始缺失记录保留，包含补测后的四种方法三题通过率均为 0%。本次修订允许的额外启动均已用完，不再重试。详细结果见各自账本及上级目录的 final_test_summary.md。
