# KineIMU Shoulder 技术报告

M6.5 本地发布候选验收报告 / 2026-09-28。作者 Hongbo Liao，软件包版本 `0.1.0`。
维护者已确认英文 README、中文报告、项目简介、MIT/CC0、版权年份 2026、
引用作者 Hongbo Liao、公开仓库目标 `TheSmashingPumpkinPies/kineimu-shoulder`。
制品验证状态、候选 ref 与后续公开发布边界见
[发布审定页](release/REVIEW.md)。本报告是已存在方法和证据的汇总，不替代规范契约。
报告编写基线 `acab57accbeee2d1fdb3cab0b6ab09c511dda0ec`；
CP3 测量源码锁和交付锁分别保留在下文，不用当前文档提交冒充数值运行源码。

## 1. 目标与交付范围

KineIMU Shoulder 为肩部康复运动分析研究提供双 IMU 采集、离线处理、
肱胸运动学、屈曲/外展分析和可复现验证。A 节点为胸廓参考，B 节点为上臂。
“经过硬件测试”指真实双设备采集层证据；“算法验证”指本文明确列出的
有限 synthetic 数值设计和 recorded replay 检查。二者不能合并为人体测量准确性。

当前 V1 不包括电池/外壳/固定产品、人体佩戴试验、志愿者或患者研究、动捕或
临床验证。输出不解释为损伤风险、疼痛、疲劳、诊断或临床结局评分。
只报告 humerothoracic movement，不声称 glenohumeral 或 scapular 角度。
依据：[范围](../PROJECT_SCOPE.md)、[ADR-008](adr/ADR-008-hardware-tested-software-complete-v1.md)。

## 2. 系统与数据流

```text
Live USB/BLE | Recorded replay | Synthetic stored sensor recordings
  → packet decode / QC / declared count-to-SI conversion
  → sensor-frame calibration → explicit sensor-to-node rotation
  → optional declared short-gap reconstruction → quaternion AHRS
  → explicit segment alignment, clock/heading support and common grid
  → relative humerothoracic kinematics → exercise segmentation / metrics
  → evidence-aware session summaries and export

Independent validation references / errors / audits remain outside production logic.
```

传输适配器保留观测，不在内部隐藏插值或重采样。生产处理、验证工具和 demo
报告分工见 [架构](../ARCHITECTURE.md)。M6 demo 调用既有 processing/1.1
stored-Q 路径，原独立 oracle 与误差检查仍参与运行；其耗时包含验证开销。

原始观测保持不可变，processed/derived 与 raw 分离。公开采集 schema 0.1、
七列 normalized IMU 表和 M1 packet/container 未改变；`run.json` 是 demo
运行记录，不作为新的公共科学交换 schema。规范入口：
[DATA_FORMAT](../DATA_FORMAT.md)、[M1 acquisition](../protocols/M1_ACQUISITION_CONTRACT.md)。

## 3. 硬件和采集证据

参考平台为两块 Seeed Studio XIAO nRF52840 Sense、板载 LSM6DS3TR-C、
Zephyr v4.4.0 与 SDK 1.0.1；board target `xiao_ble/nrf52840/sense`。
配置 ODR 为 104 Hz，与合成 sample 的 100 Hz 分开。
[固件编译证据](../firmware/xiao_nrf52840_sense/README.md)保存源码、west revisions、
SDK、配置、命令与 UF2 hashes；本轮发布包装不修改或重编固件。

[M1 1,800 s 双 USB 实测](../experiments/M1_DUAL_USB_30MIN_RESULT_20260925.md)
通过原 acquisition-stability gates。报告保留 A/B 序列计数、设备时间、主机到达
时间、原 USB 字节、accepted packet、事件与独立完整性索引。
主机到达时间不当作设备采样时间，累计设备状态和 pairwise clock 指标未测。
硬件在该门通过后冻结。

双 BLE 在当前 Windows/MediaTek controller 上仍受限，V9 正式分类为
INCONCLUSIVE。USB 通过不迁移为 BLE 通过，也不构成 BLE 根因或修复结论。
依据：[ADR-009](adr/ADR-009-dual-usb-m1-bench-fallback.md)、
[硬件边界](../HARDWARE_PROFILE.md)。安装/轴向概念见
[mounting protocol](../MOUNTING_PROTOCOL.md)，其描述不等于已验证的人体对齐。

## 4. 单位、坐标、时钟与方法

内部加速度 m/s²、角速度 rad/s、角度 rad；时间保留整数 µs，持续时间 s。
摘要角度显式显示 deg，机器产物仍按契约保存 SI。单位转换仅发生在已声明边界。

右手正交坐标、列向量、Hamilton active rotation；四元数边界为 `[w,x,y,z]`。
`R_AB` 将 B 坐标映射到 A：`v_A = R_AB v_B`。胸廓 +X anterior、+Y left、
+Z superior；上臂长轴及测试侧别使用 [M2 契约](../protocols/M2_PROCESSING_CONTRACT.md)
的明确约定，不把 sensor axes 自动认作解剖 axes。

```text
R_WT = R_WN(A) R_NT
R_WH = R_WN(B) R_NH
R_TH = transpose(R_WT) R_WH
q_TH = inverse(q_WT) ⊗ q_WH
```

固定 segment-to-node alignment 在 AHRS 后只施加一次。两个 AHRS 初始化
world 不自动相同；在相减之前需要共同 heading、时钟映射、drift 有效期和支持范围。
静态重力约束倾斜，不能识别完整 AP/ML heading。
重采样明确产生 processed grid、gap policy 和 source hashes，不按行号配对。

| 阶段 | 实现/算法来源 | 适用边界 |
|---|---|---|
| 校准 | 项目已测试的 known-pose affine/gyro bias；应用使用 imucal 2.6.0 | 校准 artifact 的身份、SI、配置和有效期需匹配；不是已测物理多姿态精度 |
| AHRS | imufusion 1.3.3 / Fusion；adapter 显式转 g 与 deg/s，逐样本设置正 dt | 六轴 yaw 漂移；声明 initialization/gap/rejection；不在 adapter 中重采样 |
| Rotation / relative kinematics | SciPy Rotation，项目 wxyz wrapper 与明确的胸廓/上臂关系 | 单位四元数、正交 proper transforms、clock/heading/alignment gates |
| 短缺口重建 | 项目已接受 processing/1.1 的 gravity-supported 单一共线速率转折模型 | 是 processed 推断；保留 bracket/time/fit/assumptions，yaw-only/不支持运动不重建 |
| 动作与 summary | M3/M4 冻结的版本化阈值、状态机及 metric 定义 | 保留 complete/partial/interrupted/excluded、分母、QC 和证据；没有临床解释 |
| Recorded segmentation | ADR-011 声明的 quality-eligible 连续区间及 AHRS 分别重启 | clipping 行仍为 null，不跨独立 worlds 组合或伪造连续恢复 |

第三方算法不是自行重写。Fusion 的 upstream 描述指向 Madgwick thesis 的修订
AHRS（chapter 7），不能简写成 initial Madgwick algorithm（chapter 3）。
本项目校准估计不能仅因使用 imucal application API 就声称执行了完整 Ferraris
物理流程。软件来源和论文导航见 [第三方声明](../THIRD_PARTY_NOTICES.md)。
项目算法依据：[ADR-010](adr/ADR-010-explicit-short-gap-reconstruction.md)、
[processing/1.1](../protocols/M5_PROCESSING_V1_1.md)、
[ADR-011](adr/ADR-011-recorded-quality-segments.md)、
[M3](../protocols/M3_KINEMATICS_CONTRACT.md)、[M4](../protocols/M4_EXERCISE_CONTRACT.md)。

## 5. 指标与证据标签

| 核心族 | 含义与报告约束 |
|---|---|
| Humerothoracic ROM | 检测动作边界内相对运动范围；不用 nominal target 替换实算结果 |
| Peak elevation | 依据 aligned humeral long axis 与胸廓的关系 |
| Repetition count | 区分有效/完整、partial、interrupted、excluded，以及验证漏检/误检 |
| Movement/phase duration | 以实际支持的时间和 phase 边界计算 |
| Hold duration | 使用版本化 hold/support 判据，缺支持值不可用 |
| Angular velocity | 明确 3-D relative angular speed / rad/s，不把 Euler 差直接当速度 |
| Rep-to-rep variability | 明确有效动作分母，sample SD `ddof=1`；CV 无量纲 |
| Thorax compensation excursion | 相对 movement-start 的胸廓 excursion proxy，有独立支持分母 |

有效性、reason、unit、evidence label 和 anatomical eligibility 与数值一起保存。
Observed 表示观测/capture/QC/time；Derived 表示处理推导；Assumed 表示声明的
构造/模型条件；Validated 仅指对应已测试数值域；Experimental 保留原实验标注。
不可用值仍为 null/invalid，不变成零或“正常”。纵向比较是支持条件一致的描述，
四条不同 exercise/side 不合并为康复效果。

## 6. 验证结果与覆盖

| 层次 | 已接受证据 | 不能推出的结论 |
|---|---|---|
| M1 | 真实 dual-USB 长时采集及不可变完整性 | 解剖准确性、BLE throughput、pairwise synchronization |
| M2 | known-input calibration/orientation/frame/time 及 deterministic replay | 人体/多姿态物理校准精度或完整 gravity heading |
| M3/M4 | synthetic kinematics、动作状态、八类指标和 evidence gate | 动捕一致性、患者准确性或 clinical score |
| M5 CP2 | 30 CLEAN E/S/Q cases 的原基线与两次独立输出 | 连续无界运动域的精度保证 |
| M5 CP3 | processing/1.1 全 1,142 frozen cases，独立审计及两次 canonical equality | 297 stress cases 不是 accuracy PASS，有限 seeds 不代表总体保证 |
| M5 CP4 | 完整 stored-Q、recorded single-node 与分段 dual-node replay；六项独立数值审计 | 真实肩部指标仍缺 timing/heading/alignment，保持 null/invalid |
| M6 CP2 | 四条 stored-Q、八流 full-chain demo，独立审核及两进程确定性 | synthetic `anatomical_eligible=false`，不是人体 demo |

M5 CP3 分类为 33 C、589 W、297 stress、122 evidence、67 boundary、34 rejection；
结果按原类别判定，不把预期拒绝或压力域处理成数值准确性通过。
完整 coverage、数值/source/tool locks、原失败与复现入口见
[M5 总报告](../experiments/M5_CP5_20260928/README.md)、
[coverage](../experiments/M5_CP5_20260928/COVERAGE.md)和
[reproduction](../experiments/M5_CP5_20260928/REPRODUCE.md)。
旧失败不改写；新 processing 的再验收不把旧产品重标为新版本。

## 7. Demo 与性能

默认输入是 [synthetic sample](../datasets/samples/m6_synthetic/README.md) 的
25 个原字节必要文件，总计 4,539,058 bytes；capture 585,136 bytes。
四轨迹 F90/AL90/AR90/T-MIX，8 streams、17,208 node-samples、4,304 packets。
这是计算负载，不能解释为人体样本量。

CP3 protocol `m6-demo-benchmark/1.1`，测量源码锁
`3e0647c4f53803abf134fee68659f63ca006e407`，交付锁
`e2c4bf26f82014ca5bde7f0deca18bd622c8062a`。
一 warmup + 五个顺序 fresh workers，每次 new output/AHRS；全部 PASS，
warmup 排除，五次全纳入，无删 outlier 或替换失败 slot。

| 端到端量 | Median | Min | Max |
|---|---:|---:|---:|
| wall time / s | 69.773776 | 63.186371 | 89.574702 |
| processing rate / node-samples/s | 246.625610 | 192.107811 | 272.337210 |

上表逐项来自 [性能报告](../benchmarks/demo/REPORT.md)及
[独立 displayed-value audit](../experiments/M6_CP3_20260928/report-values-audit.json)。
原整数 ns、全部 attempts、源码 ZIP、机器快照、audit 和失败 batch 全保留。
机器为 Windows 11 build 26200、Ryzen 7 7735H（8C/16T）、Performance scheme；
Python 3.12.14、uv 0.12.5，三个数值线程环境变量设为 1。

计时从 worker launch 前到 wait 完成后，包含启动/import、输入校验、解码/QC、
校准/AHRS、对齐/同步、M3/M4、oracle/errors、summary/hash 与 I/O。
不包含依赖安装、uv launcher 和 parent audit；pure production compute_s
为 NOT MEASURED。无实时吞吐、latency、算法纯速度或总体置信区间声明。
五次 min/max 只描述这个普通桌面 batch 的变化。
重算和新测量方法见 [协议](../benchmarks/demo/PROTOCOL.md)及
[复现](../benchmarks/demo/REPRODUCE.md)，不重复运行旧输出根。

## 8. 使用、制品与可复现性

在 Git checkout 根使用固定工具链：

```powershell
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
```

输出 `summary.md`、`run.json`、两层 checksum 和逐轨迹 processed/derived/
annotations/errors。成功共 26 files；原输入运行前后 hash 不变。
命令/路径/UTC/duration/PID 等运行字段与 canonical determinism 分别处理。
错误退出码和 new-root protection 见 [Demo 文档](M6_DEMO.md)。

wheel 提供库 API；sdist 提供重建 package 的代码及发布文档，两者均不包含
完整 repository demo/fixtures/实验记录或 Git metadata。CP4 验证两类制品在
独立 venv 的安装及真实 API 调用；CP5 另在 fresh clone/venv 验证 README
完整 demo。详见 [packaging contract](release/PACKAGING.md)及
[本轮候选制品/检查记录](../experiments/M6_CP4_FINAL_20260928/README.md)。
Linux 在本报告中 NOT RUN，Ubuntu CI 配置不是执行验收结果。

## 9. 许可、引用与剩余发布门

[ADR-012](adr/ADR-012-release-documentation-and-license-selection.md) 记录维护者
2026-09-28 接受 MIT 原创代码/文档、CC0 原创合成 sample、版权持有人 Hongbo Liao
及首发版本 `0.1.0`；后续明确同意版权年份 2026、引用作者 Hongbo Liao 和仓库 owner。
[LICENSE](../LICENSE) 为完整 MIT 正文，版权声明 `Copyright (c) 2026 Hongbo Liao`。
sample 已获公开授权，确切成员及当前条款见
[数据许可附页](../datasets/samples/m6_synthetic/LICENSE.md)；原 provenance/map/旧声明
保持原字节。第三方内容保留自己的文本和权属，原历史来源包不自动改为项目许可。
[CITATION.cff](../CITATION.cff) 填写已确认的作者、title、版本、MIT 和公开仓库目标。
实际发布日期/DOI 尚不存在而省略；机构/ORCID 按维护者要求不填。
公开仓库目标已选定，当前 origin 仍为管理仓库，不声称已发布。
依赖/算法引用见 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)。

CP4 在许可/CFF/文档一致性和新制品构建安装均验证后才能 PASS；
CP5 clean-clone 接受后才可收口 M6。当前 M0–M5 DONE、M6 CP0–CP3 PASS。
本地构建和文档草稿不声称 push/tag/Release/PyPI 已发布。
完整发布要求逐项映射见 [M6 checklist](M6_RELEASE_CHECKLIST.md)。

## M6.5 / CP5 独立收口

[CP5总报告](../experiments/M6_CP5_20260928/REPORT.md)、
[覆盖表](../experiments/M6_CP5_20260928/COVERAGE.md)及实际command/product/install records
绑定源码锁e55d68b537987f4a2cc2ac6d2ad58e15e077ed15。新clone/cache/venv，不连接设备、
不设置PYTHONPATH或外部M1数据，README两次完整演示及27,160误差标量/run独立审核通过；
同锁22规范产物及摘要一致。跨CP2锁21科学文件字节一致，摘要只替换source HEAD；
来源/路径/Python同文件别名变化明示，不放宽科学/同锁比较门。
完整877 passed/2预期外部M1 skips，与CP4维护者879/0skip分列。Ruff、mypy33、
docs/39archive hashes、whitespace、独立build/archive及两个安装venv/8命令均PASS。
收口仅修正文档检查器的过时M1 CURRENT_TASK词条；先RED的两项新控制、原docs integration
和两项provenance控制共5PASS。分析源、门限、schema、依赖、固件、sample/raw和旧证据不变。
M6本地验收DONE，首版候选仍0.1.0。Linux NOT RUN；公开仓库创建/push/tag/Release/PyPI
及大证据迁移未执行。执行源码、构建制品和最终文档交付提交分别记录，不混用其HEAD。
