# KineIMU Shoulder — 完整传感器回放 Demo

从八条已存储的 synthetic `.kimu` 流运行完整离线分析，无需设备。
全链路方法见 [技术报告](M6_TECHNICAL_REPORT.md)，输入/输出及路径规则遵循
[M6.2 / CP2 冻结契约](M6_DEMO_CONTRACT.md)。不会在线生成替代观测。

## 环境与完整演示

从仓库根执行，使用 CPython 3.12.14 和 uv 0.12.5：

```powershell
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
```

安装后，第二条命令即完整演示。首次安装需要网络或已有依赖缓存。

## 输入与输出路径

输入自动定位到 [m6_synthetic sample](../datasets/samples/m6_synthetic/README.md)，
无需 `KINEIMU_M1_RAW_ROOT`、PYTHONPATH 或设备。四轨迹为 F90、AL90、AR90、T-MIX；
共 17,208 node-samples / 4,304 packets，100 Hz synthetic；真实硬件 ODR 104 Hz 单独表述。
输入定义与原构造 provenance 见 sample README；当前公开授权以
[25-member CC0-1.0 附页](../datasets/samples/m6_synthetic/LICENSE.md)为准。

命令只提供必需的 `--output PATH` 和 `--help`。相对输出按调用 cwd 解析，
输入按脚本所在仓库定位；可从其他 cwd 用脚本绝对路径执行。
仓库内只允许顶层新的 `demo-output-*`，仓库外允许安全的新目录。
已有文件/目录、raw、input/source、旧 evidence 和仓库内容均拒绝；不支持覆盖。

## 查看结果

成功根共 26 个文件；完整布局见 [输出契约](M6_DEMO_CONTRACT.md)。

| 路径（输出根内） | 用途 |
|---|---|
| `summary.md` | 首先阅读的指标、有效性与误差摘要 |
| `run.json` / `SHA256SUMS.txt` | 本次 M6 状态、来源与顶层完整性 |
| `replay/{manifest.json,report.json,SHA256SUMS.txt}` | 原 M5 stage-B 来源、处置与 canonical 校验表 |
| `replay/cases/Q-{F90,AL90,AR90,T-MIX}/` | 每轨迹 `result.json` 和 gzip 的 `processed`、`derived`、`annotations`、`errors` JSON |

先读 `summary.md`。每轨迹包含 exercise/side、动作/排除/partial/interrupted 数量、
独立 proxy 分母、QC/校准/AHRS、来源 hash、八类核心指标、逐动作 phase/hold 支持及
原数值门的误差和支持数量。角度显示 deg，机器数据仍为 rad；速度 rad/s，时间 s/us。
每项保留 valid、reason、evidence label 和 anatomical eligibility；不可用显示
`unavailable (reason)`，不将 null/NaN 改为零。ROM 按检测到的动作边界定义；
不能把完整 nominal 90 deg 替换进导出的 ROM。SD 使用 ddof=1，CV 无量纲。

`run.json` 记录本次 M6 状态、四轨迹处置、实际 Python command、HEAD/dirty、源码及
uv.lock hash、输入前后 25 项 hash、依赖/线程环境、UTC/耗时/PID、产品 hash 和失败原因。
耗时只作运行记录；独立 CP3 性能验收见 [benchmark report](../benchmarks/demo/REPORT.md)。顶层校验表绑定其余 25 个文件，
回放校验表绑定 22 个 canonical products；两者不包含自身。

原 `replay/report.json` 保持 M5 的 `passed=false`、CP4 OPEN、`formal=false`；
该历史报告的 `stage_passed=true` 表示本次 stored-Q stage 成功。
M6 成功单独由 `run.json` 的 `demo_passed=true` 和退出码 0 表示。

## 退出和复现

| 退出码 | 含义 | 保留策略 |
|---:|---|---|
| 0 | 四轨迹、既定 gates、输入不变、摘要/清单/hash 完成 | 完整新根 |
| 1 | digest/数值/QC、危险或已有输出、处理或写入失败 | preflight 不建根；已建根保留 partial，不可在同根重跑 |
| 2 | CLI 用法错误或必要文件/依赖不可用、BLOCKED | 同上；写入不可用时 stderr 说明 |

FAILED 和 BLOCKED 同时出现时 FAILED 优先；未运行轨迹带 NOT RUN 和原因。
帮助退出 0 不表示演示成功。失败 stderr 给出处置、原因和保留根位置。

在同 HEAD、干净 tracked tree、同平台、依赖和线程环境，用两个新进程执行：

```powershell
uv run --frozen python examples/m6_demo.py --output demo-output-01
uv run --frozen python examples/m6_demo.py --output demo-output-02
```

比较全部 22 replay products、内部 SHA256SUMS 和 summary 的字节。
`run.json` 仅允许契约列举的进程元数据不同；两个顶层校验表分别验证完整性，
其余 24 项 hash 一致。完整比较规则见 [输出契约](M6_DEMO_CONTRACT.md)。
独立数值审计命令见 [复现指南](validation/reproduce.md)；历史 CP2 执行与失败记录见
[验收证据](validation/demo.md)。底层 stage-B CLI 及其独立范围见 [stored replay](M5_STORED_DEMO.md)。

## 证据范围

所有默认输入 synthetic，`anatomical_eligible=false`。校准、初始姿态、对齐、heading
和 clock 是合成构造假设；数值 gate 通过不建立人体准确性。输出保留原证据标签，
其定义与边界见 [指标文档](METRICS.md#evidence-labels-and-interpretation)。
静态重力不能给出完整 heading，独立 AHRS worlds 不自动相减。thorax excursion 是 proxy，
不合成为临床评分；四条不同 exercise/side 不合并成纵向康复效果。
无人体、临床、glenohumeral 或 scapular 准确性声明。

Demo 需要仓库的 protocols、fixtures、audit source 和 Git；wheel 单独安装不含完整资产。
Windows 是首个执行验收平台；Linux CI 增加了 smoke 命令，但实际 Linux 验收须有执行记录。
当前源码已公开；[发布状态](release/REVIEW.md)与历史验收分开记录。
benchmark 历史数值、CP4 制品验证和 CP5 fresh-clone 结果见 [技术报告](M6_TECHNICAL_REPORT.md)。
