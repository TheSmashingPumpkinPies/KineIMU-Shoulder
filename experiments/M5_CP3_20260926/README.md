# M5.3 扰动验证与 CP3 失效边界报告

**CP3：未通过。** 已执行完整冻结矩阵 1,142/1,142 用例，未运行 0 项；验收失败 46 项。
两次独立正式进程的 5,380 个canonical文件逐字节一致；独立审计通过，复核每次 13,865,857 个误差标量、独立真值、覆盖分母、来源与产物哈希。
审计通过证明结果可复算，不能替代 CP3 数值和证据门限通过。

## 验收口径

源码锁：`6f1dec791aa6e959fd41abbb46c0e7da5053601a`。契约 `m5-validation/1.0` 与完整 CP1 清单未修改。
分类：{'W': 589, 'stress': 297, 'C': 33, 'rejection': 34, 'evidence': 122, 'boundary': 67}；失败分类：{'W': 40, 'evidence': 6}。
C=精确/干净对照，W=预声明工作域，stress=压力诊断，evidence=证据控制，boundary=QC/端点边界，rejection=输入拒绝。
工作域要求每个种子同时满足全部误差门限、有效时间覆盖率 ≥98%、完整真值动作召回率 100%、误检/漏检 0；支持漂移条件的 proxy 覆盖率 100%。
工作域角度/峰值 3°、节点姿态 1°、ROM 6°、速度 6°/s、边界 100ms、时长 200ms；精确和干净对照分别沿用原门限。
覆盖率分母为完整评估真时间，包括失去的样本、无效区间和静止尾段。样本留存率、样本损失与包损失独立列出。
没有可匹配有效动作时误差 unavailable；零数值不会替代拒绝或缺失。

## 冻结扫描水平与边界口径

| 因素 | L / H / X 水平或固定配方 | 工作域与超域口径 |
|---|---|---|
| 加速度噪声 | 每轴 σ=0.005 / 0.02 / 0.20 m/s² | 短时 L/H 工作域，X 压力 |
| 陀螺噪声 | 每轴 σ=0.001 / 0.005 / 0.05 rad/s | 短时 L/H 工作域，X 压力 |
| 恒偏置 | 0.002 / 0.02 / 1 °/s；A/B/SAME/DIFF | 短时 L/H、300s L 工作域，其余压力 |
| 偏置斜坡 | 评估末端 0.004 / 0.04 / 2 °/s；校准段为0 | 同上；不能用未来数据校准 |
| 实际采样 / 仅时间戳抖动 | 整数 ±100 / ±1000 / ±6000 μs | L/H 工作域，X 压力；不修复非单调序列 |
| 样本丢失 | 首动作峰起点一行 / i>500且i%100=0 / 峰附近[-20,+40]ms | 单行与周期工作域，突发缺口拒绝 |
| 包丢失 | 峰所在包 / p>125且p%25=0 / 峰包及下一包；每包4行 | 单包与周期工作域，突发拒绝；包数独立于样本数 |
| 时钟漂移 | 0 / ±100 / ±500 / ±5000 ppm；正确仿射和错误身份映射 | 正确0/L/H工作域，X压力，错误映射诊断 |
| 航向漂移 | 0.002 / 0.02 / 0.2 °/s；传感器body-rate与世界左乘分开 | L、短时H工作域；300s H/X压力；A的已知yaw上界≤1°才有proxy资格 |
| 明示缺口边界 | 49.999 / 50.000 / 50.001 ms | 前两者AHRS接受，后者整epoch拒绝；E路径不跨缺口补值 |

这些是有限已观测扫描水平；不能推断未扫描参数上的连续安全阈值。

## 因素与实际结果

| 因素 | 用例数 | 验收失败 | 最低相对有效覆盖率 |
|---|---:|---:|---:|
| B-C | 48 | 0 | 1.0 |
| B-R | 48 | 0 | 1.0 |
| C-APPLY | 3 | 0 | 1.0 |
| C-FIT | 30 | 0 | 1.0 |
| CLEAN | 30 | 0 | 1.0 |
| D-C | 56 | 1 | 0.9957333333333335 |
| D-H | 96 | 0 | 1.0 |
| EV | 122 | 6 | 0.0 |
| GAP | 6 | 0 | 0.0 |
| I-HD | 2 | 0 | 1.0 |
| I-JL | 15 | 15 | 1.0 |
| I-NB | 15 | 0 | 1.0 |
| INPUT | 17 | 0 | 0.0 |
| J-S | 135 | 0 | 0.0 |
| J-T | 135 | 0 | 0.0 |
| L-P | 27 | 12 | 0.0 |
| L-S | 27 | 12 | 0.0 |
| M4 | 60 | 0 | N/A |
| N-A | 135 | 0 | 1.0 |
| N-G | 135 | 0 | 1.0 |

上表最低覆盖率包括预期拒绝和压力用例，因此零覆盖率本身不表示拒绝控制失败。
压力用例“完成”仅表示执行并保留局限，不能声称其准确性达标。297项压力用例中，有 237 项的 `accuracy_passed` 诊断为 false（含数值门、资格/处置门或拒绝后的不可得），这些仍完整保留。
工作域共 589 项，验收失败 40 项。最低完整有效时间覆盖率 0.999393939394，最低完整真值动作召回率 1.000000000000，漏检 0、误检 0。覆盖率门通过仍不足以抵消误差或证据门失败。

## 工作域最坏误差

| 用例 | 指标 | 最大误差 | 门限 | 误差 / 门限 | 有效覆盖率 |
|---|---|---:|---:|---:|---:|
| AL90/L-P-PER/B/0 | interval_speed | 61.223146 °/s | 6.000000 °/s | 10.203858 | 1.0 |
| AL90/L-P-PER/SAME/0 | interval_speed | 61.223146 °/s | 6.000000 °/s | 10.203858 | 1.0 |
| AR90/L-P-PER/B/0 | interval_speed | 61.223146 °/s | 6.000000 °/s | 10.203858 | 1.0 |
| AR90/L-P-PER/SAME/0 | interval_speed | 61.223146 °/s | 6.000000 °/s | 10.203858 | 1.0 |
| F90/L-P-PER/B/0 | interval_speed | 61.223044 °/s | 6.000000 °/s | 10.203841 | 1.0 |
| F90/L-P-PER/SAME/0 | interval_speed | 61.223044 °/s | 6.000000 °/s | 10.203841 | 1.0 |
| AL90/L-S-PER/B/0 | interval_speed | 60.322167 °/s | 6.000000 °/s | 10.053694 | 1.0 |
| AL90/L-S-PER/SAME/0 | interval_speed | 60.322167 °/s | 6.000000 °/s | 10.053694 | 1.0 |

误差/门限大于 1 为超限；不能按种子均值掩盖单个失败。

已观测工作域失败：AL90/AR90/F90 的 I-JL 各五种子，以及 L-S-ONE/PER、L-P-ONE/PER 的 B/SAME 目标。缺失运动节点的转折采样后，既有 AHRS 在下一保留行使用该行角速度及 dt，跨转折的旋转可能少计或多计；区间速度约 60°/s 误差，部分单包丢失还超过节点姿态 1°。这是保留产物支持的原因解释，未更改积分、补样或门限。A-only 对照通过，不能据此推广到 B/SAME。

另有1项 `F90L/D-C-H-minus-exact/B/0`（300s，−500ppm）失败于末尾不完整候选的排除理由：54个完整动作全部召回、数值误差达标、覆盖率99.9967%，但映射有效期末端的10ms缺行使候选返回 interrupted / upstream_invalid:outside_clock_validity，而缺少冻结要求的 partial_end 排除理由。每个具体漂移档和失效门均见失败表；这类处置失败不能归为速度误差。
完整逐种子数据见 [全部用例](CP3_all_cases.csv)、[失败用例](CP3_failures.csv)、[超限指标](CP3_failed_metrics.csv)、[边界扫描](CP3_failure_boundaries.csv)。

## 可观测边界与限制

- 噪声：每轴独立正态，完整种子 1103/2207/3301/4409/5519；按最大角度与速度误差验收，保留 RMSE 和每个支持行。
- 偏置：恒定与线性斜坡分别执行 A/B/同向/差分；长会话评估 300s。独立静止窗口拟合只使用 [0,5]s，不能移除后续斜坡。
- 抖动：实际采样时刻改变与仅时间戳错误分开；超域非单调时间在 AHRS 拒绝，禁止用 nominal Hz 修复。
- 丢样/丢包：原始序号不重排，样本与包计数独立。50ms 等号接受；超过 50ms 的完整未分 epoch 输入由 AHRS 拒绝。精确姿态路径只在缺口支持处失效，不能跨缺口补数值。
- 缺口等号附近的运动转折可以保留 100% 覆盖而仍出现速度误差超限；这是预声明 QC 边界用例的数值诊断，不是工作域准确性证明。
- 时钟漂移：正确下游仿射映射不改变 AHRS 的 device dt；错误身份映射保留误差与来源，无法靠六轴姿态自动识别虚假映射证据。
- 航向漂移：传感器体角速度注入和世界姿态左乘路径分开；已知 A 节点 yaw 上界超过 1° 时 proxy 排除，肩部相对指标按自己的门限验收。同向世界 yaw 的相对角不变也不升级世界/proxy 资格。
- 证据控制失败 6 项：heading、A/B clock-map 三类引用的 E/S 路径接受了有效格式但不匹配的全零来源摘要。raw 文件 hash、CRC、node ID 控制通过；失败的是证据引用绑定，不能虚构生产拒绝。
- 非预期执行异常 0 项。现有阶段、reason、可用消息和已完成节点结果保留在逐例记录中。

## 复现与证据

正式运行根：`./experiments/M5_CP3_20260926/formal4`，两个 run 根均不可覆盖。
大型文件为 deterministic gzip（mtime=0）封装 canonical UTF-8/LF JSON；哈希指向实际压缩文件。测试运行时间与日志在 operational 中，不参与数值字节比较。
1,064 用例直接执行 pipeline；78 个用例复用完整冻结 M4/M2 构造，绑定 196 项真实收集的断言及对应 clean 控制，不能把这些精确构造当作 noisy AHRS 等号准确性证据。
完整结果与文件索引见 [正式结果摘要 — historical availability](../../docs/PUBLIC_EVIDENCE.md#not-distributed-in-this-source-snapshot) 与 [独立审计](reproducibility.json)。

```powershell
.venv/Scripts/python.exe examples/m5_perturbation.py --output <fresh-run-root> --workers 4
.venv/Scripts/python.exe experiments/M5_CP3_20260926/audit.py --root <two-run-parent> --output <new-external-audit.json>
```

项目检查：完整pytest 612 passed、2个既有外部M1数据skip（359.79s）；16项CP3集成回归均纳入。Ruff、严格mypy（25源码文件）、文档一致性与空白检查通过。硬件、M1 raw、公开 schema、生产算法、冻结 CP0/CP1 与 CP2 runner 均未改变。
本结论限于有限合成数值和证据验证；不代表物理、人体或临床准确性。CP4、CP5 与整体 M5 保持开放。

## 执行与保留记录

前三对停止的formal1/2/3产物及其来源版本和逐文件哈希已完整保留；正式完整证据为formal4双运行。此前一次与扫描并行的全量测试出现OpenBLAS内存分配失败（611 passed、1 failed、2 skipped），扫描结束后隔离重跑全量测试通过。正式扫描期间临时调整本任务活动工作进程数并全部恢复，仅影响调度；源码、输入、backend和数值环境未改。

Git retention anchor is recorded in committed-evidence.json after commit verification. No formal root may be resumed or overwritten.

Retained-evidence Git commit: `82551792bb895782e4b36fa686093a166c7cb7d3`. [Git blob retention proof](committed-evidence.json) verifies every canonical byte and identical run1/run2 Git maps.

Public-export note: unavailable internal navigation is redirected to the evidence-availability index; scientific claims and original target names are retained by the export record.
