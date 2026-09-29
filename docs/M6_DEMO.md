# KineIMU Shoulder — 完整传感器回放 Demo

M6.2 / CP2 入口，遵循 [冻结契约](M6_DEMO_CONTRACT.md)。
在含 Git 元数据的仓库 clone 中，从八条原始合成 `.kimu` 流开始，实际执行
packet 解码、QC、SI 转换、校准、AHRS、显式节点/节段对齐、clock/heading/common-grid、
M3、M4 分段与指标、thorax proxy 和 session summary。没有连接硬件或在线生成替代观测。

## 一次命令

从仓库根执行，使用 CPython 3.12.14 和 uv 0.12.5：

```powershell
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
```

安装后，第二条命令即完整演示。首次安装需要网络或已有依赖缓存。
输入自动定位到 [m6_synthetic sample](../datasets/samples/m6_synthetic/README.md)，
无需 `KINEIMU_M1_RAW_ROOT`、PYTHONPATH 或设备。四轨迹为 F90、AL90、AR90、T-MIX；
共 17,208 node-samples / 4,304 packets，100 Hz synthetic；真实硬件 ODR 104 Hz 单独表述。
所选原创 sample 已获公开授权，采用
[CC0-1.0 数据许可附页](../datasets/samples/m6_synthetic/LICENSE.md)。
sample README 提供当前使用说明；原字节 provenance 中的许可字段描述授权前的
构造时点，当前授权以许可附页为准。

命令只提供必需的 `--output PATH` 和 `--help`。相对输出按调用 cwd 解析，
输入按脚本所在仓库定位；可从其他 cwd 用脚本绝对路径执行。
仓库内只允许顶层新的 `demo-output-*`，仓库外允许安全的新目录。
已有文件/目录、raw、input/source、旧 evidence 和仓库内容均拒绝；不支持覆盖。

## 查看结果

成功根共 26 个文件：

```text
demo-output-01/
  summary.md
  run.json
  SHA256SUMS.txt
  replay/
    manifest.json
    report.json
    SHA256SUMS.txt
    cases/Q-{F90,AL90,AR90,T-MIX}/
      result.json
      processed.json.gz
      derived.json.gz
      annotations.json.gz
      errors.json.gz
```

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
run.json 仅 output path、command 的 output 参数、UTC、duration、PID 允许不同；
两个顶层校验表分别验证完整性，其余 24 项 hash 一致。
CP2 实际执行/独立审核/失败记录见 [验收证据](validation/demo.md)。

## 证据范围

所有默认输入 synthetic，`anatomical_eligible=false`。Observed 是 capture/QC/time；
Derived 是算出的指标；Assumed 是已知 synthetic calibration、initialization、alignment、
heading 和 clock；Validated 仅指 M5 已测试 synthetic domain 的原门；Experimental 原样保留。
静态重力不能给出完整 heading，独立 AHRS worlds 不自动相减。thorax excursion 是 proxy，
不合成为临床评分；四条不同 exercise/side 不合并成纵向康复效果。
无人体、临床、glenohumeral 或 scapular 准确性声明。

Demo 需要仓库的 protocols、fixtures、audit source 和 Git；wheel 单独安装不含完整资产。
Windows 是首个执行验收平台；Linux CI 增加了 smoke 命令，但实际 Linux 验收须有执行记录。
CP3 benchmark 已独立通过；CP4 文案/许可/作者/仓库身份已明确接受，
候选构建及安装验证 (complete record retained in the local evidence archive) 单独留证。
CP5 fresh clone/fresh environment 验收已通过；报告及证据 (complete record retained in the local evidence archive)
记录两次完整Demo、独立审核、full877+2预期skip和新环境检查。Linux NOT RUN，公开发布尚未执行。
