# M6 Demo Contract — KineIMU Shoulder

契约标识：`m6-demo-contract/1.0`。2026-09-28 M6.0 / CP0 规格冻结。
适用范围：clean-clone、离线处理的双节点 **synthetic stored-Q replay**。
入口基线：`main` / `566ce905e7fea5ddbc2f33b3432c68fd0c2b6907`。
本契约定义输入、输出和支持范围；历史验收见技术报告，当前候选校验单独记录。

依据：M6 计划 (complete record retained in the local evidence archive)、[验收要求](../ACCEPTANCE_CRITERIA.md)、
[M5 processing/1.1](../protocols/M5_PROCESSING_V1_1.md)、
[M5 validation/1.0](../protocols/M5_VALIDATION_CONTRACT.md)、
[CP0 实测盘点](../tests/fixtures/demo/input-inventory.json)。
本契约只冻结输入分发、调用、展示及验收边界；不改公开采集 schema 0.1、
生产 API、指标定义、算法、门限、依赖、旧证据或已接受 ADR。
M6 `run.json` 是演示运行记录，不作为新的公共科学数据交换 schema。

## 1. 输入及分发决定

默认读取以下 **25 个原字节必要文件**，保留于 `datasets/samples/m6_synthetic/`，
另加 README 和来源清单。默认入口只从该仓库相对路径读取，不回退到外部磁盘、
原 `.venv`、`KINEIMU_M1_RAW_ROOT` 或本机 CP1 绝对路径。
原来源 `datasets/samples/m6_synthetic` 保持只读。

| 文件族（sample 根相对路径） | 数量 | 用途及消费者 |
|---|---:|---|
| `SHA256SUMS.json` | 1 | `input_audit` 独立锚定原 map，再审核选定文件 |
| `annotations.json` | 1 | 独立 nominal M4 / summary / motion 参考；不作为传感器观测 |
| `observation-labels.json` | 1 | 冻结观测标签身份，`input_audit` 绑定；loader 不直接读取其数值 |
| `case-manifest.json` | 1 | 每轨迹选择 `CLEAN-Q/SAME/0` 的冻结参数 |
| `manifest.json` | 1 | 原生成来源/模型/backend 身份；保留历史 CP1 状态 |
| 每个 F90 / AL90 / AR90 / T-MIX 下的 `A.kimu`, `B.kimu` | 8 | 唯一的实际传感器观测；M1 解码、计数、QC、sensor SI |
| 每轨迹 `metadata.json` | 4 | R_NS、R_NK、校准、初始 q_WN、clock construction |
| 每轨迹 `A-si.json`, `B-si.json` | 8 | 独立 pre-Q SI / time / retention；量化审核及构造时间身份 |

必要输入共 **4,539,058 bytes**，其中 capture 共 **585,136 bytes**。
这是盘点规模，不是性能结果，也不包含 sample README/来源清单及仓库代码。
每个文件的精确 bytes、SHA-256 和 Git 字节匹配见上述 inventory 的 `inputs`。
原 map SHA-256：
`2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9`。
原 manifest 记录生成 HEAD `ee0741334e430c7cf8b5b9845d0a9b48426fecad`；
原 CP1 完成交付及生成工具来源继续引用原 CP1 README/锁，不把生成入口 HEAD 当完成验收锁。

原 map 有 36 个条目；sample 保留原 map 字节但只提供上述 24 个成员加 map。
其余 12 个成员不属于 `input_audit` 的必需集合。不得声称 sample 是原 run1
完整副本或所有 map 成员都已分发；CP1 来源清单明确列出选定及未分发成员。
不重写 map、不去重同 hash 的 A 文件、不缩减成单轨迹、不在线再生成观测。
原 sample 的历史 INTERNAL ONLY 标签保留；当前已批准的 25-member CC0 授权以 [许可附页](../datasets/samples/m6_synthetic/LICENSE.md) 为准。

| 默认顺序 | 运动/侧别 | 节点角色 | 每节点输入 | 数值验收支持 |
|---|---|---|---|---|
| F90 | flexion / left | A thorax、B humerus | 538 包、2,151 样本 | 三次完整动作 |
| AL90 | abduction / left | 同上 | 同上 | 三次完整动作 |
| AR90 | abduction / right | 同上 | 同上 | 三次完整动作 |
| T-MIX | flexion / left，移动 thorax | 同上 | 同上 | 三次动作及胸廓 proxy |

总计 8 个节点流、4,304 包、17,208 node-samples。各流 device time 为
0–21,500,000 us，单 epoch、完整 sample sequence 0–2150、无 QC issue。
100 Hz 合成输入与真实硬件 104 Hz ODR 分开表述。
数值评价窗口 5–21.5 s，segmentation context 0–21.5 s；初始 0/5 s 单独审核。
21.5 s 轨迹长度、5 s warmup 及 16.5 s evaluation 是输入定义，不是运行耗时。

## 2. 现有调用接口及仓库依赖

下列接口在入口 HEAD 已实际 import / inspect；全链路沿用已验收 M5 实现。

| 接口 | 输入 → 输出 | 调用/副作用边界 |
|---|---|---|
| `stored_demo.input_audit(input_root: Path)` | 完整 25 文件 → `{relative_name: sha256}` | 只读；map 变更/成员失配 ValueError，缺文件/无权限抛 I/O 异常 |
| `stored_demo.run_stored(trajectory, workspace, *, input_root=CP1_ROOT)` | 四种受支持 ID 中一个 + 完整输入 → 含 processed/derived/errors 的 dict | 不保护 workspace；不生成 capture；不能作为用户入口；保留独立标签和错误计算 |
| `stored_demo.export_stored(output, *, input_root=CP1_ROOT)` | 四轨迹完整输入 → 新目录及返回 int | 先 `_protect`、再 exclusive mkdir；顺序运行全部四条，独占写文件；无 CLI input-root 参数 |
| `replay._protect(output, inputs)` | resolved path + 独立 anchors → None 或异常 | 只判断，不建目录；已存在根 FileExistsError；受保护路径 ValueError |

M6 薄包装调用 `export_stored(output / "replay", input_root=sample_root)`；
不直接复制 `_session`，不改 `CP1_ROOT` 常量或 M5 CLI，不 monkeypatch 原审核。
`_session` 是 validation 私有组装接口；不能将其升级为通用生产 API。
原 CLI 当前可用：

```powershell
uv run --frozen python -m kineimu_shoulder.validation.stored_demo --output demo-output-m5-reference
```

它仍读取原 CP1 路径、输出 M5 stage B；CP0 没有运行这条全链路命令。

Exporter 除输入外还读 40 个仓库文件：32 个 package `.py` 和以下 8 项。
逐项源码 bytes/hash 见 inventory 的 `exporter_dependencies`。

- `uv.lock`
- `protocols/M5_VALIDATION_CONTRACT.md`、`protocols/M5_PROCESSING_V1_1.md`
- `tests/fixtures/M5_KNOWN_SENSOR_MOTIONS.md`、`tests/integration/test_m5_stored_demo.py`
- `validation/auditors/synthetic.py`、`validation/auditors/stored.py`
- `docs/M5_STORED_DEMO.md`

这些非 package 文件用于 manifest 身份绑定；exporter 还调用 Git 获取 HEAD/dirty。
因此支持契约是 **含 Git 元数据和这些文件的 clone**。当前 wheel/sdist 单独安装
不包含完整 repository demo 所需资产，不能宣称 wheel-only 或 source ZIP 解压即可演示。
CP1 包装只搬选定输入，不删除原 experiments 中 exporter 的来源依赖。

## 3. 阶段、接口与可观察证据

| 阶段 | 既有调用及转换 | CP2 必须可观察的产物/拒绝条件 |
|---|---|---|
| 输入身份 | `input_audit`；运行前/后审核 | map 和全部成员一致；缺失/篡改明确拒绝 |
| packet / QC / sensor SI | `replay_capture` + M1 count adapter | original hash、node ID、单 epoch、538/2151、端点/序列；half-LSB 审核；无新 `.kimu` |
| sensor calibration → node | `apply_calibration`，identity M / zero bias，再 R_NS 一次 | `calibration_executed=true`；calibrated force/rate、artifact/hash |
| 显式 processed reconstruction | `reconstruct_short_gaps`，max gap 0.05 s | 原行不变、model provenance；clean-Q inferred rows 为零；不藏在 adapter |
| node AHRS | `estimate_orientation`，fresh imufusion，known initial q_WN | `ahrs_executed=true`、normalized quaternion；无 exact E 路径替代 |
| segment alignment | `align_segment`，q_WK=q_WN·q_NK 一次 | alignment/hash，R_NK 不重复；known synthetic shared world |
| 显式 clock / heading / grid | `relative_orientation` + `ClockMap` / `HeadingRelation` | 10,000 us grid、50,000 us gap 上限、2,000 us timing uncertainty 上限；source refs/valid/reason |
| M3 | `long_axis_elevation`、`relative_angular_speed` | 长轴 elevation / geodesic interval speed；quaternion relative，非 Euler 代用品 |
| M4 segmentation / metrics | `segment_shoulder_repetitions`、`compute_repetition_metrics` | candidates、phase/hold boundaries、partial/excluded reasons、有效分母 |
| thorax proxy / session | `prepare_thorax_common_grid`、`compute_thorax_excursion`、`summarize_exercise` | proxy 独立 validity/分母；summary evidence strata，非临床评分 |
| 独立参考 / report | existing O/F/T oracle、nominal labels、stored exporter | 原始逐项 error/support/门限和标签交叉核对；原 result/report 保留 |
| M6 展示 | 薄包装读上述产物 | 八类指标、身份、单位、QC、限制及运行成功/失败清楚可读 |

采用 active scalar-first Hamilton quaternion `wxyz`、右手列向量；R_AB 映射 B→A。
sensor SI → R_NS node → AHRS q_WN → R_NK segment → common world → R_TH。
thorax +X anterior/+Y left/+Z superior，H +Z proximal。具体语义沿用 M2/M3 契约。
resampling/SLERP 是显式 processed stage；raw timestamps 保留，host arrival 不是 sample time。

## 4. M6 目标命令、环境及退出行为

以下入口 **CP2 待实现**；CP0 只冻结命令，不声称已可执行。
从候选 ref 的 fresh clone 根目录，使用 CPython 3.12.14 / uv 0.12.5：

```powershell
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
uv run --frozen python examples/m6_demo.py --output demo-output-02
uv run --frozen python examples/m6_demo.py --help
```

最小 CLI 仅 `--output PATH`（必需）和 `--help`；不提供单轨迹、真实 raw、
生成器、force/overwrite 或可改算法参数。相对 output 从调用 cwd 解析为绝对路径；
sample 从脚本所在 repository root 解析。示例从根目录执行，不设 PYTHONPATH。
成功 stdout 给出四轨迹完成、summary 相对位置和 synthetic 范围；失败 stderr
给出 disposition、原因和已保留根位置（若已创建）。不硬编码性能耗时或解剖准确率。
依赖安装需要网络/缓存；hardware-free 不等于首次安装离线。

| exit | M6 包装入口语义 | 输出策略 |
|---:|---|---|
| 0 | 全部四轨迹、所有既定 gate、输入不变和 M6 摘要/运行清单/hash 完成 | 完整新根；`demo_passed=true` |
| 1 | digest/数值/QC gate 失败、非法/已存在 output、意外处理/写入失败 | preflight 失败不创建根；已创建则保留 partial、不得重跑该根 |
| 2 | argparse 用法错误，必要文件/依赖不可用或无读取权限，BLOCKED | 同上；没有可写权限时 stderr 足够，不强求写失败记录 |

CLI `--help` 为 exit0 的帮助路径，不是 Demo 成功。捕获 I/O/processing 异常后
不能把缺文件降级成空/零值成功；mixed failure 与 BLOCKED 时 exit1 优先。
每条轨迹 disposition 包括 complete/FAILED/BLOCKED/NOT RUN；未执行轨迹必须有原因。

原 exporter exit0 只代表 stage B passed；其 `report.passed=false`、CP4 OPEN、
`formal=false` 保持原样。M6 用 `stage_passed`、4 个 case、zero failed/blocked、
完整产物与输入 hash 验证自己的 `demo_passed`。pre-mkdir `_protect` 及 Git/manifest
异常可能直接抛出；M6 包装负责转换成上述退出行为，不假定 exporter 全部异常都被捕获。

路径 preflight 先 resolve（含 symlink/junction 目标），拒绝已有文件/目录、repository
根、任意 `raw` 组件，以及受保护目录本身、后代和包围它们的祖先。
沿用 `_protect` 的 datasets/firmware/package/tests/input/existing evidence 防护，
M6 额外保护完整 sample/source input root、`.git`、`.agents`、`.codex`、docs、scripts、
examples、benchmarks、protocols、integrations、`.github` 等仓库内容；仓库内部只允许
顶层新的 `demo-output-*`（benchmark 包装允许新的 `benchmark-output-*`）。
仓库外的安全新目录可用；不存在与路径安全必须在 exclusive mkdir 时再次成立，
不得把 exist_ok=True 或关闭原防护作为实现。CP0 probe 只证实现有保护，M6 加强保护待 CP2 验证。

## 5. 输出契约与确定性比较

成功根共 26 文件，布局冻结如下（失败可为有原因的 partial）：

```text
demo-output-01/
  run.json                 M6 运行身份、状态、command、source/input/runtime/hash
  summary.md               可读摘要，引用 replay 相对路径
  SHA256SUMS.txt           顶层索引，绑定另外 25 文件，排除自身
  replay/
    manifest.json          原 m5-report/1.0：HEAD/dirty/source/runtime/config
    report.json            原 M5 stage B 状态；不改写历史 checkpoint
    SHA256SUMS.txt         原 exporter 索引：绑定其 22 canonical products
    cases/Q-{F90,AL90,AR90,T-MIX}/
      result.json
      processed.json.gz
      derived.json.gz
      annotations.json.gz
      errors.json.gz
```

gzip 为原 canonical JSON、mtime=0；SI 机器数值维持 rad、rad/s、s/us、m/s²。
没有额外生成 capture。`run.json` 至少保留 contract ID、demo_passed、exit/disposition、
四轨迹状态、processing/metric versions、source HEAD/dirty及包装/源文件/uv.lock hashes、
input-root及 25 项 before/after hashes、完整 command、runtime/dependencies/thread env、
开始/结束/耗时、产品相对路径/hash、failed gates、限制。未完成的字段明确 unavailable。
源码、输入和原 manifest 状态不能由包装摘要的成功标记替代。

CP2 两个独立新进程，在同 HEAD、干净 tracked tree、同输入/依赖/OS/thread config 下比较：
**全部 22 replay canonical products、其内部 SHA256SUMS 及 summary.md 字节相同**。
`run.json` 的 output absolute path、command output argument、UTC times、duration、PID
允许不同；这些是完整列举的运行变化字段，不允许数值/valid/reason/hash/版本变化。
顶层 SHA256SUMS 因 run.json 改变而不同；两次分别校验其完整性，并比较其余 24 项 hash。
跨 HEAD、input-root、平台或源码 CRLF/LF 字节差异不要求旧 provenance 全字节相等。
CP2 必须检查实际导出是否满足该集合，不能未验证就用任意字段排除掩盖差异。

## 6. 展示八类指标及证据边界

每条轨迹列 exercise、side、candidate/valid/excluded/partial/interrupted count、
error/coverage denominator、proxy valid/unavailable count；指标逐项保留 valid/reason、
unit、definition version、evidence_label、anatomical_eligible。summary 从机器产物读值，
不可用显示 `unavailable (reason)`；JSON null/内存 NaN 不改为零。

| 核心家族 | 既有字段/位置（derived） | 展示及分母 |
|---|---|---|
| humerothoracic ROM | `repetitions[].metrics.rom_rad`；`summary.statistics.rom_rad` | deg 展示/rad 原值，有效完整 rep |
| peak elevation | `peak_elevation_rad` | deg；有效 rep |
| repetition count | `summary.detected_count/valid_count/excluded_count` | 次数，各种 partial/exclusion 单列 |
| movement/phase duration | `rep_duration_s/elevation_duration_s/return_duration_s` | s；phase boundaries us 保留 |
| hold duration | `hold_duration_s`、`hold_runs_us` | s；无 hold 与不可用区分 |
| angular velocity | rep/elevation/return/hold `speed_mean_rads/speed_max_rads` | rad/s，若展示 deg/s 明示转换 |
| rep-to-rep variability | `summary.rom_range/rom_sd/rom_cv` | deg/deg/dimensionless；sample SD ddof=1，n<2 理由 |
| thorax compensation excursion proxy | `proxy[]` extension/lateral_flexion/axial_rotation；summary `thorax_*` | deg；独立有效分母/heading/drift 限制，不合成评分 |

Observed 指原 capture/时序/QC 观测；Derived 指经过明确计算的结果；Assumed 指
known calibration/initialization/alignment/heading/clock 等构造条件；Validated 只在
对应 M5 tested synthetic domain 的既有 gate/evidence 上使用；Experimental 保留原
输出标签。不能为界面整齐而重标每个值为 Validated。所有默认输入 source_type=synthetic，
`anatomical_eligible=false`。没有真实人体、临床、glenohumeral 或 scapular 准确性声明。
静态重力不确定完整 heading；独立 AHRS worlds 不能自动相减。

默认三次动作的 nominal ROM/peak 90 deg、rise 1.5 s、hold 1 s、return 2 s，
是冻结 fixture/annotation 的真值，不要求 Q 估计值精确等于它。
CP2 使用 unchanged clean S/Q budgets：orientation/initialization 0.4 deg、角度/proxy
1 deg、interval speed 2 deg/s、duration 0.10 s、boundary 50 ms；全部既定 aggregate
和 support gates 仍适用。每轨迹 truth=valid=3、missed=false=0、relative/proxy coverage=1；
errors 保留 1,651 elevation / 1,650 interval-speed evaluation supports。
预算的完整定义以 M5 contract、fixture 和现有 runner 为准，不仅检查这段摘录。
无独立证据的真实 replay 肩部输出仍为 null/invalid；该补充输入不进入默认 Demo。

既有 `compare_summaries` 支持有 provenance/comparability 的跨会话比较；默认四条
不同运动/侧别不得合并为纵向康复效果。CP2 无新增趋势算法或额外 longitudinal UI。

