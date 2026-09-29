# M5.4 — 不可变记录回放与证据门控分步计划

日期：2026-09-27。最新执行状态见 CURRENT_TASK.md。D2 源码准备检查点：维护者已批准 ADR-011 显式分段处理；完整运行结果由新根证据及动态状态记录。原失败 D 不变。CP4/CP5 仍需独立 E/总验收。
原状态：A/B/C已交付。D在干净源码锁6a305eed下完整原始A/B入口实际运行exit1：B原始sample1604645带GYRO_CLIPPED且X=-509.04deg/s，被既有校准门控拒绝；B AHRS/双流下游NOT RUN，独立审计exit1。11项清单未变，失败产物完整保留。full718/no skips、focused45及静态检查通过不代表D通过。D FAILED；CP4/CP5 OPEN，E NOT RUN。
规划基线：`main@33d75e304b55e90ea1843d3f745bc9bb01ccf968`。
维护者要求：先规划，再分步推进，不一次性交付。

2026-09-27 维护者明确采纳[分段契约](protocols/M5_RECORDED_SEGMENTS_V1.md)
（ADR-011）：D2 完整保留原始行，对削顶/超量程行输出 null，有效连续区间
分别通过原校准并重启 AHRS。D 验收改为完整质量感知回放、原始计数守恒及
所有有效区间重算审计；不声称全部原始行获得有效姿态，不跨参考世界拼接。
仅重新验收 D，保留原 D FAILED；C、合成路径、CP0–CP3、门限及硬件不变。
E 后续两进程审计须明确使用此 D 策略，本段仍止于 D。

## 依据与边界

遵循 [M5 总计划](M5_DEVELOPMENT_PLAN.md)、
[冻结契约](protocols/M5_VALIDATION_CONTRACT.md) 的 immutable replay/launch 章节、
[processing/1.1](protocols/M5_PROCESSING_V1_1.md) 和
[ADR-010](docs/adr/ADR-010-explicit-short-gap-reconstruction.md)。
CP0–CP3 已验收；此次不重定义真值、门限、公共采集 schema 或硬件。
验证逻辑留在 validation、测试和实验工具中，复用既有 M2/M3/M4 接口。
不新增采集，不以真实记录声称肩部准确性，不使用 host arrival 虚构同步。
M5.5 总验收及 M6 发布包装不属于本次交付。

## 输入与已完成的规划预检

2026-09-27 已只读核对以下三个原始流及外部清单的 SHA-256；均匹配既有锚点。
这仅证明入口可访问和字节身份，不构成回放或 CP4 通过。

| 输入 | 锚点 | 允许输出 |
|---|---|---|
| 合成落盘 Q demo | 冻结 F90/AL90/AR90/T-MIX、CP1 源及独立标注 | 标记 synthetic 的完整链路、独立误差与门限结果 |
| 留存 Node B | `firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu`；`1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201` | 完整记录 QC、时序、计数、示例校准下的节点姿态；肩部 unavailable |
| M1 USB A | `<external-data>/kineimu_m1_usb_30min_20260925_01/raw/node-a.kimu`；`9e929d0ac025ea3b7322c3a48668e5f21c83fd7372ba920709c18f124f328db5` | 完整原始流独立回放、节点姿态、门控报告 |
| M1 USB B | 同根 `raw/node-b.kimu`；`0ae3f1aa712b915bf5b0f4381cb2391b3619d41bbbc2fe81152f5d32c0e5bc68` | 完整原始流独立回放、节点姿态、门控报告 |

外部 `SHA256SUMS.txt` 锚点：
`219a7a2cf07eb962ee3bf4755dc0a49d4ccf48447bb27be1edc08d55f5529ea7`。
全清单 11 项必须在正式入口预检及回放后核验，不能只检查两个 kimu。
计数、端点和时序期望引用
[M1 bench 报告](experiments/M1_DUAL_USB_30MIN_RESULT_20260925.md) 与既有
`tests/integration/test_m2_replay_m1_bench.py`，不能从新 runner 结果反推期望。

## 五段推进及停点

每次只推进一个连贯阶段，汇报该段证据及下一动作后停点交接。
正式运行必须等工具测试与源码锁完成；阶段进展不等于 CP4 通过。

| 阶段 | 工作与交付 | 该段验收与停点 |
|---|---|---|
| A — 入口、报告与门控测试 | 梳理 CP1 Q demo、CP2/CP3 全链路和 M2 replay 可复用接口；固定 CP4 用例到验收要求的映射；先写报告完整性、错误 hash/node、缺证据、输出防覆盖及路径保护测试；实现最小验证 runner | 独立期望驱动的 red/green 证据；真实输入缺失返回 BLOCKED/NOT RUN；不在 raw 或已有 formal 根写入；此段不执行正式长记录 |
| B — 合成落盘 demo | 从冻结 Q 源完整读取 F90/AL90/AR90/T-MIX 双节点落盘数据，经 QC、校准、显式同步/对齐、AHRS、M3/M4 到报告；绑定独立标注、量化和预热规则 | 全部指定轨迹的误差、计数、覆盖率及 evidence 符合冻结门限；没有以内存真值替代实际回放；保留开发运行产物，此时 CP4 仍 OPEN |
| C — 留存 Node B | 完整 832 样本回放，报告原计数/端点/QC、校准假设和节点姿态；验证单节点输入的下游 unavailable | 原始 hash 前后一致，完整范围明示；无双节点肩部数值；测试缺证据理由经真实接口传播到最终报告。已有 M2 前 128 样本示例不能替代此段 |
| D — 真实 M1 双 USB | 对 11 项清单做只读完整性预检，完整回放 A/B 两个约 30 分钟流，各自校准/AHRS；把 clock/common-heading/alignment/drift 缺失交给既有门控并输出报告 | A 46,943 包/187,772 样本、B 47,856 包/191,424 样本及端点匹配原锚点；真实输入不得补造同步/对齐；肩部指标明确不可用。实际执行记录命令、exit code、输入/产物 hash；无文件或权限为 BLOCKED，skip 不算通过 |
| E — CP4 正式留证与验收 | 在干净已提交源码锁下启动两个独立进程，各执行完整 B/C/D 输入集合；两个此前不存在的输出根；独立核验全部 canonical 字节、完整输出清单、输入前后 hash、证据等级和拒绝理由；完成项目检查 | 每个必须输入实际运行、全部门槛通过、两次 canonical 字节一致、原始清单及源 hash 未变，才能标 CP4 PASS；交接 M5.5，CP5 和整体 M5 仍 OPEN |

正式根路径/运行 ID 在 E 启动前冻结并确认不存在。开发结果不替代正式证据。
任何失败或中止保留 partial、完整 hash 清单及失败原因；重试采用新根并引用旧证据。
不追加或修补旧正式根以制造 PASS。运行日志和耗时与 canonical 产物分开。

## CP4 必须逐项核验

1. 原始不变：每次读取前后 SHA-256 对照；外部完整 11 项清单及清单自身 hash 一致。
2. 实际回放：完整落盘 demo、完整 Node B、完整 M1 A/B 均有运行及报告证据。
3. 门控正确：真实记录缺 clock/common-heading/alignment/drift 的事实和既有 reason
   保留到最终报告；numeric null、valid=false，不产生获救的肩部数值。
   单项缺证据的隔离测试使用合成/测试副本，不改真实输入。
4. 假设透明：示例 identity 校准和独立节点 world 是 Assumed/Experimental；
   static gravity 不提供共同 yaw。节点姿态不升级为解剖或临床 Validated。
5. 合成符合真值：独立冻结标注及 Q 量化预算、完整分母、候选排除和误差支持均可核对。
6. 重复一致：两独立进程全部 canonical 文件逐字节相等，输出清单无漏项。
7. 来源完整：记录 exact source HEAD、dirty 状态、源码 map、contract/truth/manifest、
   配置、uv.lock、backend/runtime、源数据及产物 hash；遵循 m5-report/1.0。

## 验证与阶段交接

规划段仅运行 docs consistency 与 `git diff --check`；不声称数值验证。
实现段先执行对应 focused tests，再运行以下要求；每次 basetemp 使用新目录。

```powershell
.venv/Scripts/python.exe -m pytest --basetemp .tmp-m54-<stage>-<run> --tb=short
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy --strict kineimu_shoulder
.venv/Scripts/python.exe scripts/check_docs_consistency.py
git diff --check
```

D/E 另设置 `KINEIMU_M1_RAW_ROOT` 指向上述只读根，记录已有 M1 集成测试的实际
通过结果和 CP4 完整节点 AHRS/下游门控报告。既有 M2 解码测试本身不覆盖后者。
若发现生产缺陷，先独立回归测试、记录依据及受影响再验收范围，不放宽冻结门限。
每段提交有效工作，更新 CURRENT_TASK、必要时 PROJECT_STATUS，覆盖 HANDOFF，
追加 CHANGELOG_DEV；记录实现锁/证据提交锚点、检查结果和精确下一动作。

阶段 A 已交付，源码/证据锚点 `abbadda9802029c4a4659c193e492ca0d69ba5b0`；见
[入口与覆盖映射](docs/M5_REPLAY_ENTRY.md) 和
[阶段 A 验证记录](experiments/M5_CP4_STAGE_A_20260927/README.md)。
当前下一动作：C 已到停点；维护者继续时进入 D 的完整外部11项清单/M1双USB记录回放。
阶段 A 的停点已完成；维护者已授权第二段 B。阶段 B 完整留存开发运行后停点，CP4 仍 OPEN。

阶段 B 已交付：源码锁 `1da000de1b0652379504572479dc40c993f18696`，四条完整双节点留存 Q 回放通过；[独立审计与验证记录](experiments/M5_CP4_STAGE_B_20260927/README.md)。B 开发通过不构成 CP4 验收；D/E 尚未执行。

阶段 C 维护者于 2026-09-27 授权进入。[完整 Node B 接口与限制](docs/M5_RECORDED_NODE.md)
明确区分独立节点 AHRS 与单节点同流拒绝探针：后者仅调用现有 M2/M3/M4 缺证据门控，
不产生 A 流、解剖对齐、共同时间网格或肩部数值。C 的留存开发运行根冻结为
`experiments/M5_CP4_STAGE_C_NODE_B_20260927`，启动前必须确认不存在；记录到
`experiments/M5_CP4_STAGE_C_20260927`。失败保留原根，重试必须用新根。C 结束后停点。

C 已交付：源码锁 `84cbeed40bf357ca686316c2195293215335cd6e`，完整原计数/时间/SI/AHRS及
真实门控理由审计通过，raw hash前后一致，无肩部数值；[留存证据](experiments/M5_CP4_STAGE_C_20260927/README.md)。
D/E 仍 NOT RUN；不以 C 开发exit0接受CP4。

D真实完整尝试已失败并留证：[失败根因与交接](experiments/M5_CP4_STAGE_D_20260927/README.md)。不能剔除原始flag或放宽量程门控来补齐AHRS；维护者需先决定显式processed处理契约，再用新源码锁/新根重试。D未交付，E不得启动，CP4/CP5保持OPEN。
