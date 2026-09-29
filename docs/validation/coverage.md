# M5 要求—用例—证据覆盖

依据 [M5 验收条款](../../ACCEPTANCE_CRITERIA.md)、
CP5 条件 (complete record retained in the local evidence archive) 与
CP0 冻结审查 (complete record retained in the local evidence archive)。下面四行逐条覆盖 M5 验收；
后表展开算法、边界和证据门控。历史报告中的“下一 checkpoint OPEN”
是当时状态，当前状态由总报告与 CP5 最终检查给出，历史文件不修改。

| M5 验收原条款 | 用例/检查 | 保留证据及结论 |
|---|---|---|
| rotations、transforms、filters、segmentation、metrics、edge cases 的 unit tests | M2 frame/calibration/orientation/relative；M3 elevation/speed/ROM；M4 C/P/T/U；M5 O/F/T/P/G、INPUT/GAP/EV/M4 | 下表测试、完整 pytest 日志；既有 pinned AHRS 是 filter，无独立额外 smoothing 需求；CP0 审查明确不发明滤波模块 |
| known ROM、reps、tempo、holds、velocity 的 deterministic ground truth；noise、bias、jitter、packet loss、drift | CP1 独立 source/oracle；CP2 30 CLEAN E/S/Q；CP3 全部 1,142 有限用例及种子 | CP1 (complete record retained in the local evidence archive)、CP2 (complete record retained in the local evidence archive)、CP3 (complete record retained in the local evidence archive)；工作域内 0 未解决失败，stress 保留局限 |
| M1/demo recording 经 preprocessing/orientation/kinematics/exercise/report 的 replay validation | CP4 B 的 Q-F90/Q-AL90/Q-AR90/Q-T-MIX；C REC-NODE-B；D M1-A/M1-B 的所有原始行及下游诊断 | 正式 pair audit (complete record retained in the local evidence archive) 与 formal2/run1、run2；demo 有数值真值，真实记录由既有缺证据门控走到 null/invalid 报告；实际外部 M1 运行，无 skip 替代 |
| errors/robustness 的 source/configuration provenance；synthetic 标识 | per-case errors/result/annotations、每 seed 行、两次 canonical map；代码锁、配置、运行环境及依赖锁 | CP2/CP3 report 和 manifest、CP4 manifest/source ZIP/tool ZIP，`evidence-index.json` 逐文件 SHA-256；source_type=synthetic 或 recorded、anatomical_eligible=false；无临床升级 |

## 细化覆盖

CP2 `retry1/run1/report.json` 的 `requirement_index` 映射每一类别到精确 case
ID，`evidence_index` 定位行级/rep级文件。CP3 `formal1/run1/report.json` 的
`requirement_index` 映射以下 family 到全体 ID，每条 `results[].artifacts`
绑定 gzip processed/derived/annotations/errors 和 result 的 hash；CSV 总表
CP3_all_cases.csv (complete record retained in the local evidence archive) 保留全部行。
机器索引保留这些索引，不以抽样或单个例子替代完整矩阵。

| 要求 | 参考/用例入口 | 回归测试及最终证据位置 |
|---|---|---|
| SI、四元数、旋转方向、非交换组合、一次性对齐 | CP1 O0–O5、F/T；CP2 E/S/Q | `tests/unit/test_m2_frames.py`、`test_m2_orientation.py`、`test_m5_source.py`；CP1 manifest，CP2 processed/errors |
| 校准参数应用、独立静止拟合、初始化/收敛与偏置 | O6、C-APPLY/C-FIT、B-C-/B-R-/C-；5s warmup 单独报告 | `test_m2_calibration.py`、`test_m2_orientation.py`、`tests/integration/test_m5_perturbation.py`；CP3 result/annotations/processed |
| 显式 clock map/SLERP、真实 dt、gap、epoch | J-S-/J-T-/D-C-/GAP-/INPUT-/EV- | `test_m2_relative_orientation.py`、`tests/integration/test_m1_clock_mapping_synthetic.py`；CP3 时间支持、coverage 和拒绝 reasons |
| humerothoracic elevation/ROM/peak/3-D speed | F90/AL90/AR90/VAR/F90L/T-MIX E/S/Q；CP3 相应轨迹 | `test_m3_elevation.py`、`test_m3_angular_speed.py`、`test_m3_interval_rom.py`；CP2/CP3 errors，CP4 Q errors |
| repetition count、wrong plane、partial/invalid | QUIET/WRONG/PARTIAL/F90-30；M4-、INPUT-/EV- | `test_m4_segmentation.py`、`tests/integration/test_m5_baseline.py`；matched/unmatched truth 与 excluded candidates |
| movement/phase/hold/rest duration 与速度 | F1/F4/F5 的平台保持/无保持/非对称节奏、VAR 等冻结轨迹；M4-P fixtures | `test_m4_metrics.py`；CP2/CP3 result/errors，物理 support 与 M4 阈值 envelope 分开 |
| variability、SD/CV、near-zero、session comparison | VAR、F90/F90-NEXT、M4-U、EV-comparison | `test_m4_summary.py`；CP2 两项比较、CP3 fixture/evidence 结果；重映射/处理版本不混池 |
| thorax-compensation excursion proxy | T-MIX/T0/T1、M4-T、EV trace/drift/singularity/branch | `test_m4_thorax.py`；CP2/CP3 proxy errors/reasons；不转成 clinical score |
| noise / bias / jitter / sample 与 packet loss / drift / interactions | N-A-/N-G-、B-C-/B-R-、J-S-/J-T-、L-S-/L-P-、D-C-/D-H-、I- | CP3 全部 family/target/seed；reconstruction 保留 original-row conservation 和观测可辨识性审计 |
| evidence 缺失、过期、错误身份、assumed、null | EV- 全 122、INPUT/GAP/M4 fixtures；CP4 C/D | `tests/integration/test_m5_replay_entry.py`、`test_m5_recorded_node.py`、`test_m5_recorded_segments.py`；numeric null+valid=false+原 reason |
| 完整不可变落盘输入和不跨重启世界 | CP4 Q 四轨迹；Node B 832；M1 A/B 379,196 行 | `test_m5_stored_demo.py`、`test_m5_recorded_dual.py`、`test_m5_formal_replay.py`；E4 六项独立数值审计及原输入快照 |
| absent-root/严格退出/来源锁/两独立进程/错误审计拒绝 | CP1/CP2/CP3/CP4 两根与独立 audit；E3/E4 worker/source guards | `test_m5_source_export.py`、`test_m5_baseline.py`、`test_m5_perturbation.py`、`test_m5_formal_replay.py`；E4 guard 文件的 8 项测试；CP5 hash 错误控制 |

## CP5 自身 gate

| gate | 可复查证据 |
|---|---|
| CP0–CP4 齐全、每个输入与两次输出完整 | `evidence-index.json` 的 checkpoint/source/artifact/文件 map；`evidence-audit.json` 核对完整库存与既有 hash |
| 全部必需检查通过 | `checks.json` 的实际 command、exit、log hash；full pytest 两项外部实际测试、审计 guards、Ruff、strict mypy、docs、whitespace |
| 无未解决工作域失败 | CP3 report 的 failed/not_run=0，589 W 同时检查 errors/counts/coverage；297 stress 单列；旧 46 失败对应完整再验收结果 |
| 未覆盖内容有明确依据 | M6_HANDOFF.md (complete record retained in the local evidence archive)；ADR-008 的人体/临床/穿戴排除与 M6 待验收事项 |

没有必需 M5 条款标为未执行或用不适用规避。额外 smoothing/硬件构建、人体
ground truth 及 release packaging 的不适用/后续理由分别来自既有架构、
本段无固件改动、ADR-008 和 M6 验收边界。
