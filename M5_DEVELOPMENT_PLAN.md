# M5 Development Plan — Synthetic and Replay Validation

日期：2026-09-28（Asia/Shanghai）。状态：**M5.0–M5.5 / CP0–CP5 在各自验收范围通过；M5 DONE，M6 尚未验收**。
收口入口：[M5 总报告](experiments/M5_CP5_20260928/README.md)、
[要求—用例—证据覆盖](experiments/M5_CP5_20260928/COVERAGE.md)、
[复现命令](experiments/M5_CP5_20260928/REPRODUCE.md)、
[限制及 M6 输入](experiments/M5_CP5_20260928/M6_HANDOFF.md)。
CP0 冻结契约；CP1 已交付验证边界内的合成源、独立 oracle 和回放输入。
证据：[CP1 报告](experiments/M5_CP1_20260926/README.md)、[CP2 全链路报告](experiments/M5_CP2_20260926/README.md)。
CP2 的 30 个干净 E/S/Q 用例与两项比较达标；两次独立进程全部 131 文件字节一致。
仅为冻结合成数值/证据范围；[源解释差异](experiments/M5_CP2_20260926/SPEC_NOTES.md) 已记录。
冻结交付物：[验证契约](protocols/M5_VALIDATION_CONTRACT.md)、
[独立传感器运动真值](tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md)、
[CP0 审查](experiments/M5_CP0_REVIEW_20260926.md)。

本计划落实 [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) 的 M5、
[VALIDATION_PLAN.md](VALIDATION_PLAN.md) 的 Layer 1–3，以及
[ADR-008](docs/adr/ADR-008-hardware-tested-software-complete-v1.md)。
范围、接口和算法语义仍以规范文件为准；本计划不改变公开 schema 或已接受的 ADR。

## 目标与入口

M5 要交付可复现的验证证据：从有独立真值的双节点传感器输入，经预处理、
校准、AHRS、显式对齐/同步、M3、M4 到报告；量化受控扰动下的误差、
可用性和拒绝行为；再用不可变真实记录验证回放与证据门控。

入口基线：M0–M4 在各自记录的证据范围内 DONE。
规划起始 HEAD：`02901e80dfd02603ffadb55772600748f9cb1bb4`（`main`）。
[M4 CP5](experiments/M4_CP5_20260926/README.md) 从精确的对齐后姿态开始，
没有执行传感器校准/AHRS，因此不能替代本次传感器级全链路验证。

硬件继续冻结。仅屈曲及左右侧外展、既定八类核心指标；不加入人体采集、
动捕、临床验证、平滑度新算法、泛化关节模型或新运行时依赖。
任何新算法或生产缺陷修复须独立记录依据、先写测试，再复跑受影响 checkpoint。
M6 的 UI、发布包装和完整 release benchmark 留在 M6。

## 阶段交付与 checkpoint

阶段顺序为 CP0 → CP1 → CP2 → CP3 → CP4 → CP5。
每阶段按“测试/真值 → 实现 → 证据报告 → 状态更新/提交”完成，不能以代码存在代替放行。

| 阶段 | 目标与交付物 | Checkpoint / 放行条件 |
|---|---|---|
| **M5.0 — 冻结验证契约与矩阵** | 建立 `protocols/M5_VALIDATION_CONTRACT.md`、`tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md` 和 CP0 审查报告；定义轨迹、观测模型、独立真值、扰动层、幅度、种子、误差门限、证据门控与报告格式；映射既有单测到 M5 验收要求。 | **CP0：规格放行。** 每项要求有用例 ID、输入层、独立参考、单位、预期数值或拒绝理由、验收门限；数值门限有推导依据且在运行前冻结。审查 M2/M3/M4 兼容性；不虚构真实记录的同步/对齐证据。CP0 已完成规格冻结；哈希和审查见 CP0 报告，数值验证尚未执行。 |
| **M5.1 — 传感器级合成源及独立 oracle** | 在独立 validation 边界实现双节点已知运动源，生成 SI 加速度/角速度、原始时间、标注和来源清单；构造可回放的落盘 demo 输入。保留精确姿态路径作为隔离对照。 | **CP1：真值工具放行。** 验证重力符号、旋转方向、非平凡传感器轴/段对齐、左右侧、非交换双体运动、时间映射、采样/量化规则；解析角速度/姿态一致，零扰动守恒；固定配置/种子生成同样字节；独立 oracle 不调用被测 M3/M4 计算结果作为真值。 |
| **M5.2 — 无扰动全链路基线** | 合成传感器 → 既有校准/AHRS → 显式对齐/同步 → M3/M4 → processed/derived/report；建立干净输入的误差表。覆盖屈曲、左右外展、静止、非对称节奏、平台保持、移动胸廓、错误平面及部分动作。 | **CP2：干净输入放行。** ROM/峰值、计数、阶段/保持时间、3-D 角速度、变异性、胸廓 proxy、会话比较满足 CP0 的分层门限；对应 QC/evidence/null 正确；报告初始化/收敛段。两次独立进程输出一致；保留 M4 精确输入的原门限，无放宽。 |
| **M5.3 — 受控扰动与失效边界** | 单因素扫描噪声、偏置、时间抖动、样本/包丢失、时钟漂移与航向漂移；增加预先指定的少量交互组合和固定种子重复。输出误差、有效覆盖率、漏检/误检、候选排除与分层边界表。 | **CP3：鲁棒性放行。** 工作域内用例同时满足误差与最低有效覆盖率；超域用例按契约明确拒绝/降级或记录已知限制。边界两侧、单节点/双节点扰动、短/长时段均有证据；所有用例有结果，不能只汇总幸存有效动作或删除失败种子。 |
| **M5.4 — 不可变记录回放与证据门控** | 双节点合成落盘 demo 完整回放；仓库留存 Node B 记录和外部 M1 双 USB bench 只读回放。报告源/hash、计数、时间、QC、校准假设、节点姿态及下游可用/不可用理由。 | **CP4：回放放行。** demo 完整链路符合独立标注；真实记录按证据能力处理，缺 clock/common-heading/alignment 时肩部指标不可用；同一输入重复回放一致，前后原始 hash 不变；外部 M1 正式回放实际执行并留证。缺文件/权限只能标 BLOCKED/NOT RUN，不能凭 skip 宣称 CP4 通过。 |
| **M5.5 — 验收报告与交接 M6** | 形成 M5 总报告、要求—用例—证据索引、可复现命令、保留的两次运行、测试覆盖缺口说明、已知限制与 M6 输入清单；刷新用户文档和动态状态。 | **CP5：M5 收口。** CP0–CP4 证据齐全；完整项目检查通过；canonical 输出与输入/配置/代码/锁文件 hash 可核对；每条 M5 验收要求均有对应证据或明确不适用依据；没有未解决的工作域内失败。只宣称已测试条件下的 synthetic/replay 验证。 |

上述 CP0 三个路径已创建并冻结；CP1 源、oracle、完整清单和量化 demo 已交付；CP2 无扰动全链路与重复性已交付。
CP3 按已授权的 [processing/1.1](protocols/M5_PROCESSING_V1_1.md) 和
[ADR-010](docs/adr/ADR-010-explicit-short-gap-reconstruction.md) 完成再验收：
两次独立运行均通过全部 1,142 个冻结用例，规范字节一致，独立审计通过。
[新版证据](experiments/M5_CP3_UNBLOCK_20260927/README.md) 保留全部原始输入、真值、种子和门限，
[旧失败证据](experiments/M5_CP3_20260926/README.md) 保持留存。CP4 已通过实际双进程完整回放与独立审计；CP5 已完成要求覆盖、完整性核对和必需项目检查，详见总报告。
不预建空模块；复用既有 replay、calibration、orientation、relative orientation、
M3/M4 及 export 接口，验证逻辑留在 `kineimu_shoulder/validation/`、测试和实验报告中。

## CP0 必须冻结的决策

1. **两层真值。** 一层用解析/独立四元数姿态隔离 M3/M4；另一层用连续已知
   双体轨迹生成传感器观测并运行 AHRS。不得把生成器与生产函数的同源错误互相验证。
   记录 `q_WT`、`q_WH`、`q_TH` 和 sensor→node→segment→world 的方向及一次性对齐。
2. **传感器观测模型。** 明确加速度是 specific force、重力符号、运动线加速度
   是否为零、传感器位置/杠杆臂假设和初始姿态。角速度从独立解析轨迹或旋转增量得到；
   曲线导数、采样时刻及 AHRS 的首样本无积分规则必须一致。
   M1 packet/count 格式回放另计量化误差；理想 SI 输入不得冒充实际硬件测量。
3. **轨迹与标注。** 每种练习规定侧别、幅度、上升/保持/下降/休息、采样网格、
   起止状态和胸廓轨迹。物理运动边界与 M4 阈值确认/候选边界分开标注；
   边界偏差须由既有阈值及采样规则推导，不能把整个真实运动时长直接当 M4 rep duration。
4. **门限与依据。** 精确输入继续使用 M3/M4 的既有门限；传感器级门限独立建立，
   由时间分辨率、量化、已接受的 backend 精度和明确的工程预算支撑。
   M2 的 `3e-5` Cartesian component 用例门限不能直接当作 ROM/hold 误差门限。
   在 CP0 写出 rad、rad/s、s 的具体值、有效覆盖率下限和每个边界的预期行为。
5. **AHRS/校准条件。** 冻结 pinned backend 设置、首样本、预热/收敛窗口、
   重置与 gap 限制、校准适用范围。校准验证区分“已知参数正确应用”、
   “独立静止校准段估计偏置”和“未校正残差”；不从运动评估段反推参数以消除误差。
6. **重复单位。** 单位为轨迹×扰动配置×种子的一次完整 session；帧和同一 session
   内的 reps 不当作独立实验。固定有限种子清单和每种因素独立随机流；
   不以大量 Monte Carlo 替代确定性边界测试。若开展多种子汇总，保留每个 seed 行。
7. **报告/运行协议。** 冻结配置版本、输出版本、canonical JSON/null、文件 map/hash、
   目录不得存在/拒绝覆盖、严格错误退出及报告层次。新验证报告不是公开采集 schema 变更。
8. **覆盖审计。** 列出现有 rotations/transforms/filter/backend/segmentation/metrics
   测试及证据；仅补足缺口，避免复制已完成 M2–M4 单测或重实现成熟算法。

## 扰动矩阵与结果解释

以下概述覆盖类别；**具体幅度、日程、有限种子和门限已在 CP0 契约落盘**，
正式扰动验收仍须先通过 CP1/CP2。所有因素以 SI 或显式整数时间单位记录。

| 因素 | 注入层与对照 | 必须检查的结果 |
|---|---|---|
| 加速度/角速度噪声 | 传感器 SI 层；零噪声、工作域低/高强度、超域压力；每轴分布/幅度/seed 明示 | 角度/速度误差、阈值附近候选与 hold 变化；不是硬件噪声测量 |
| 恒定 gyro bias / 时变 bias | 传感器层；A-only、B-only、同向/差分；未校正与独立校准段校正对照 | 初始误差与随时长累积的误差分开；不把真实运动当静止偏置消除 |
| 时间抖动 | 区分“实际采样时刻改变且重新计算观测”和“时间戳误差但观测时刻不变” | 使用实际 dt；严增、重复、倒序、gap 阈值等号及两侧；不能用 nominal Hz 掩盖 |
| 样本丢失 / packet loss | 合成副本；预定单点/周期/突发 mask；包级注明 samples-per-packet 与原 sample/packet sequence | 两类丢失分别计数；缺失峰值/保持/起止的影响；禁止跨长 gap 补样或连接候选 |
| 相对 clock drift | 独立 device→common 仿射 scale/offset；精确映射、错误/过期/缺失映射对照 | 同步残差与下游误差/证据资格；device clock 漂移与 heading 漂移分开 |
| 六轴 heading drift | 传感器 bias 积分路径；另设明确标注的姿态级注入以隔离下游 | common/differential yaw、持续时长/漂移资格门控、plane 和 thorax proxy 的局限 |
| 小型交互组 | 预先声明 noise×bias、jitter×loss、heading-drift×duration 的组合及匹配基线 | 能看见单因素未暴露的相互影响；不推断未测试组合，不要求误差逐点单调 |

额外确定性边界：空/静止、单个动作、起止半个动作、错误平面、阈值等号、
近零 CV、胸廓分解奇异性、无效样本/饱和、时钟 epoch 重置、过期/remount 对齐、
会话不兼容。沿用现有契约的异常/不可用行为，不创建一套冲突的“自动修复”策略。
AHRS 对坏时间/超限 gap 的既有整 epoch 拒绝规则仍有效；若切 epoch，须显式记录边界及重置。

报告至少按条件保留：truth 总 reps、detected/valid/excluded reps、匹配规则、
误检/漏检与 reason、有效样本/动作覆盖率、每个有效匹配的误差和最坏误差。
没有可匹配有效项时误差为 unavailable，不能写 0。
工作域通过必须同时满足误差和覆盖率，不能靠全部拒绝输入获得通过。
压力用例可记录算法局限；只有契约明确可观测且应拒绝的情况才要求自动拒绝。

## 记录回放的证据分级

| 输入 | 可检验内容 | 不可声称内容 |
|---|---|---|
| M5 新生成并落盘的双节点 demo | 已知模拟 clock/common heading/alignment 的完整 pipeline、独立标注误差和 canonical 重放 | 物理或人体准确性；模拟证据始终标 synthetic |
| 仓库留存 Node B `.kimu` | 已钉住 hash、原时序/计数/QC、示例校准下的节点姿态和重放一致性 | 双节点运动、肩部 ROM/计数、真实校准准确性 |
| M1 双 USB 30 分钟原记录 | 两个原始流独立回放、校验清单、时间/QC、节点姿态、下游缺证据拒绝和完整报告路径 | 通过 host arrival 对齐推得的肩部准确性、测得的共同航向或 anatomical alignment |

实际输入锚点：

- 仓库记录：`firmware/xiao_nrf52840_sense/evidence/node_b_20260913_stationary.kimu`；
  SHA-256 `1abc499b99a1b2b0b81c91c62bf3113ac1b5633a41c887391b3456c8590cc201`。
- 外部只读根：`<external-data>/kineimu_m1_usb_30min_20260925_01`；
  `KINEIMU_M1_RAW_ROOT` 为既有测试入口。
  原始 A/B hash、清单及可测边界见
  [M1 bench 报告](experiments/M1_DUAL_USB_30MIN_RESULT_20260925.md)。
- 已有回放门控：`tests/integration/test_m2_replay_recorded.py`、
  `tests/integration/test_m2_replay_m1_bench.py` 和 `examples/m2_offline_replay.py`。

CP4 的真实输入路径走到报告时，M3/M4 gate 应输出明确 unavailable/rejected 状态。
这属于证据门控集成验证，不是完成有数值输出的真实肩部运动分析。
若做显式 assumed 映射的敏感性展示，必须独立于正式 replay gate，不能升级证据等级。
真实记录没有运动独立真值，不计算“准确率”；只报告可核对的工程事实、确定性和限制。
合成丢包/故障注入只操作派生副本，保留 parent hash 与注入 manifest，绝不改 M1 raw。

## 每阶段验证、失败处理与交接

规格/规划文档段：运行 docs consistency 和 whitespace 检查，不宣称数值验收。
CP1–CP5 实现段：运行对应 focused tests 后执行完整必需检查：

```powershell
.venv/Scripts/python.exe -m pytest --basetemp .tmp-m5-<stage>-<run> --tb=short
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy --strict kineimu_shoulder
.venv/Scripts/python.exe scripts/check_docs_consistency.py
git diff --check
```

`<stage>` / `<run>` 是执行时替换的占位符。每次使用新的测试临时目录，保留既有 scratch。
真实外部回放需另记录设置 `KINEIMU_M1_RAW_ROOT` 后的实际通过结果；默认 skip 不构成证据。
固定 Python/uv/`uv.lock` 及 backend 版本；不为规划引入 DOE/统计新依赖。

每个 checkpoint 报告记录执行命令、exit code、pass/skip/fail、工作树/代码 HEAD、
输入/配置/contract/truth/锁文件和输出 hash、环境、已知限制和下一动作。
内容确定性在同一冻结环境内检查；时间戳/运行耗时等非确定性日志与 canonical 数值产物分开。
所有输出保留 SI、validity/reason、source type、Observed/Derived/Assumed/Experimental；
Validated 只在已通过的具体测试条件/层次上使用，不能升级为物理解剖或临床验证。

遇到工作域内失败：保留结果，定位到输入模型/参考/接口/算法；新增独立回归测试后修复。
禁止事后放宽门限、修改既有 truth、删失败 seed 或静默修改原始数据。
若确实需要改变契约，记录版本、理由、已有授权及重新验收范围；公开 schema 变更另需 maintainer approval。

每个连贯阶段后提交有效工作；更新 `CURRENT_TASK.md`、必要时更新 `PROJECT_STATUS.md`，
覆盖 `HANDOFF.md`、追加 `CHANGELOG_DEV.md`，记录确切实现 HEAD 和下一动作。
检查未通过时不跨 checkpoint，不提前标记 M5 DONE。

**下一动作：M5.4 / CP4 不可变记录回放与证据门控。**
CP3 再验收仅覆盖有限合成扰动矩阵及显式重建模型假设，不表示真实记录或整体 M5 已通过。
按上表执行合成落盘 demo、仓库 Node B 记录和实际外部 M1 双 USB bench 回放，
保留源哈希、证据缺失的明确拒绝、重复性及报告。外部数据跳过不能通过 CP4；完成 CP4 后再执行 CP5。

## M5.4 / CP4 accepted — 2026-09-28

Two independent complete B/C/ADR-011 D runs and six independent numeric audits passed. [Accepted CP4 evidence](experiments/M5_CP4_STAGE_E4_20260928/README.md) retains canonical equality, originals, exact numerical/audit-tool locks, explicit source-EOL/worker identity proof and all original failed attempts. M5.4 DONE; CP5/overall M5 OPEN. Next separately authorized M5.5; no hardware acquisition or M6 launch.
