# M6 输入、已知限制及覆盖缺口

M5.5 交付 M6 的输入清单；M6 实现和 release 验收尚未启动。
按 [M6 验收要求](../../ACCEPTANCE_CRITERIA.md) 与
[路线图](../../02_DEVELOPMENT_ROADMAP.md) 继续，不重新设计 M0–M5。

| M6 输入 | 可复用位置 | 下一步必须确认 |
|---|---|---|
| 完整 hardware-free synthetic pipeline | `examples/m5_baseline.py`；CP1 四条 Q demo；CP4 B 完整回放 | 从 clean clone 安装 frozen dependencies，选一个最小完整 demo，形成清晰的一次运行入口和预期报告；不得依赖本机外部 M1 数据 |
| 经过验收的数值与质量边界 | CP2 report、CP3 完整表/独立 audit、CP4 E4 audit，CP5 COVERAGE/index | 保持 synthetic/recorded、SI、validity/reasons 和 evidence 标签；新处理版本需重新验收，不能抹去 provenance 差异 |
| 可公开的示例输入与 provenance | CP1 F90/AL90/AR90/T-MIX；仓库留存 Node B；对应 hash/labels | 确认 sample dataset 的大小、许可及打包方式；外部双 USB 30min raw 不作为 clean-clone 运行前提，不自动复制或公开 |
| 技术报告与限制 | 本总报告、M2/M3/M4 报告、hardware/protocol/backend 文档 | 汇总 release 技术报告和 usage；纠正历史 open 状态时保持旧实验不可变 |
| reproduction 和 source-byte identity | REPRODUCE、CP3 86 项 source ZIP、CP4 63 项 source ZIP/独立 tool ZIP | clean-clone 检查与精确旧锁复现分开记录；不同 Git/运行 source hash 不声称 canonical provenance 全字节相同 |
| Python/tooling/依赖 | pyproject.toml、uv.lock、Python 3.12.14 / uv 0.12.5 | CI/安装/打包/示例复验；有意更改依赖要单独记录并复验 |
| release governance | LICENSE、CITATION.cff、THIRD_PARTY_NOTICES 需求 | 检查是否齐全且一致，完成许可证/引用/第三方声明；CP5 不宣称已经 release-ready |
| 性能证据 | 既有 validation logs 只证明检查完成 | M6 独立设计可复现 benchmark，记录输入规模、机器、命令、配置/版本和结果；不得把 pytest 耗时当分析吞吐或性能数字 |

## 保留限制和缺口

| 项目 | 已知证据 / 未覆盖内容 | 对 CP5 与 M6 的影响 |
|---|---|---|
| 合成物理模型 | 连续解析运动、零平移/杠杆臂假设、有限轨迹/种子/扰动强度；不覆盖全部组合或真实人体运动 | CP5 在冻结有限设计内通过；M6 声明 tested domain，不能推广到任意动作/患者 |
| heading 与 timing 的可观测性 | 静态重力不决定 yaw；隐藏 bias 和错误但看似可信的 clock map 不能由六轴 AHRS 自动识别 | stress 记录误差/coverage；不能声称自动安全拒绝，真实 A/B 不提供肩部数值 |
| 校准与 anatomical alignment | known synthetic 参数及示例 identity 校准；没有真实多姿态校准、佩戴对齐/动捕真值 | 保持 Assumed/Experimental 和 anatomical_eligible=false；不声称临床 ROM 准确性 |
| 显式 short-gap reconstruction | ADR-010 的重力支持、局部共线单转换模型；不恢复 yaw-only、不可观测或任意动态 | 输出原始 brackets/fit/model provenance；不得隐藏在 adapter、用于原始数据修复或宣称任意缺运动可恢复 |
| recorded 质量分段 | ADR-011 保留 B index23297 null；A 一世界、B 两个新世界 | 不跨世界延续/配对；保持 clipping/range reason，不重新开放硬件 |
| 真实肩部真值 | M1/Node B 是采集/节点回放证据，无独立运动标注、共同时间/heading/alignment | 真实 recording 的准确率不适用；null 是验收规定行为，不改写为 0 或成功肩部测量 |
| CP2 参数解释差异 | VAR prose 与参数/CP1 标签第三起点不一致；synthetic UTC 只作排序标签 | [SPEC_NOTES](../M5_CP2_20260926/SPEC_NOTES.md) 已记录；保持冻结字节，未来修订需新契约版本，不阻断当前已审查解释的 CP5 |
| backend settings/平台 | imufusion API 不暴露 defaults getter；determinism 在 pinned Windows 环境实测 | 不虚构有效 defaults；跨平台/新版本 canonical 一致性尚未建立，M6 clean-clone 必须另验 |
| 自动测试范围 | unit/integration 与已冻结 known-input 全部覆盖；没有新人体/硬件采集 | M5 无必需未解决测试缺口；更广泛物理/跨平台覆盖是限制，不能由 test count 代替 |
| BLE 和可穿戴/人体/临床 | USB gate 不证明双 BLE 吞吐通过；battery/enclosure/wearability/human/mocap/clinical 均在 ADR-008 外 | 公开说明；保持 hardware freeze，不纳入 M6 UI 或 V1 新门槛 |

## 精确下一动作

下一工作段先读取 SOURCE_OF_TRUTH、PROJECT_STATUS、CURRENT_TASK、HANDOFF，
运行 `git status --short`、`git branch --show-current`、`git log -5 --oneline`、
`python scripts/agent_context.py`。按 CP5 留存索引核对 HEAD/证据，不改旧根。
然后进入 M6.0：盘点上述 demo、sample dataset、文档、许可、引用与 benchmark
缺口，制定小步骤及 clean-clone 验收命令，再做最小 hardware-free demo/release
包装。无物理操作、采集或硬件重开要求。
