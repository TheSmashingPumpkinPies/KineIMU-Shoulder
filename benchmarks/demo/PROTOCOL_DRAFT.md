# M6 Demo Benchmark — preregistration draft

2026-09-28 / CP0 草案 `m6-demo-benchmark-draft/1.0`；**尚无 runner 或性能结果**。
CP3 在任何正式测量前冻结 `benchmarks/demo/PROTOCOL.md`、runner 和 source lock，
登记偏离原因；本草案不能当成 CP3 PASS。依据 [Demo 契约](../../docs/M6_DEMO_CONTRACT.md)
及 [M6 计划](../../M6_DEVELOPMENT_PLAN.md)。不改变 numerical budgets。

## 工作负载与计时范围

固定四条 F90/AL90/AR90/T-MIX、8 个 Q streams；完整 17,208 node-samples、4,304 包。
输入必需集合 25 文件/4,539,058 bytes，capture 585,136 bytes；正式输入须通过
CP1/CP2，保留原 map `2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9`。
禁止换 seed、裁剪窗口、只算一轨迹、只计有效行、把精确 E 姿态当同一负载。

| 计时项 | 开始 / 结束 | 包含 / 排除及发布条件 |
|---|---|---|
| 必需 end-to-end `wall_s` | 父进程 `perf_counter_ns` 紧邻启动 Demo Python child 前 / child wait 返回后 | 包含进程启动、imports、hash、读取/解码/QC、校准、reconstruction、AHRS、M2/M3/M4、现有 oracle/error 计算、报告/hash 写入；不含 uv sync、安装、父进程后置独立 audit/统计 |
| 可选 production compute `compute_s` | 已加载、审核的观测进入 calibration 前 / M4 session summary 返回后 | 只有可可靠隔离 production 调用且排除 oracle、errors、I/O/hash 的已测试边界才启用；不得从 end-to-end 减估计 overhead 得到 |

默认只发布 end-to-end：现有 `_session` 交错生产计算与 oracle、summary 复核也调用
生产算法，不能把 exporter 用时标成纯算法用时。CP3 如不能可靠隔离，将 compute_s
明确标 NOT MEASURED，不新增计时钩子/算法变更来凑结果。Demo 的 run.json duration
可作辅助诊断，正式 wall_s 以父进程边界为准，单位 s，ns 原值保留。

可计算 `node_samples_per_s = 17208 / wall_s`，标为串行四轨迹**端到端处理率**。
分母含上述验证开销；分子包括全部节点样本，不只 evaluation/有效样本。
不称 live throughput、实时延迟或 realtime factor；不把四条时间线当一条同步采集。
不计 hardware acquisition/等待/安装；pytest 用时不是 benchmark。

## 环境与预定执行

固定 source HEAD、clean tracked tree、uv.lock/输入/runner/wrapper/contract 全 hash。
记录 OS/build/arch、CPU 型号/逻辑核数、内存、Python 3.12.14、uv 0.12.5、所有实际
依赖版本、进程 worker 身份、启动命令、working directory、存储位置及环境变量。
OPENBLAS_NUM_THREADS、OMP_NUM_THREADS、MKL_NUM_THREADS 均设为 1，并在每个 child
imports 前固定；记录可用 BLAS/threadpool 身份，不虚构不可读取的 backend defaults。
报告机器电源模式及同时运行任务等可观察背景；未观察字段写 unavailable。

正式批次前：CP2 正确性/独立审核已通过，同锁 fresh child 做一次完整 warmup，
其输入/产物/hash/exit/log 同样保留。warmup 失败则批次 FAIL，五次 timed NOT RUN。
之后按固定顺序做 **五次 timed attempts**，每次新 Python 进程、新输出根、fresh AHRS；
禁止并行、复用内存状态或重用根。OS cache 不清空；这是 warm-cache 条件，
不能把 fresh process 表述为 cold disk cache。wall_s 只计 Python child，不计 uv launcher。

目标命令（CP3 待实现，从 clone 根目录；依赖预先安装）：

```powershell
uv sync --extra analysis --frozen
uv run --frozen python benchmarks/demo/run_benchmark.py --output benchmark-output-01
```

runner 使用当前 `sys.executable` 启动 `examples/m6_demo.py --output <fresh-child-root>`，
默认读取冻结 sample。输出新根按 Demo 同等防护，拒绝已有根/源码/原证据。
warmup 与 timed01–05 是该批次下的新 child roots；runner metadata 不在 child 计时中。
父进程独占保留 stdout/stderr、命令、start/end、wall_ns、PID/exit。
任意失败保留原 attempt，仍记录其耗时和原因；无有效产物则不能进入成功统计。
五次预定 slots 全列出；如无法继续，明确 NOT RUN 原因。不可补跑替换失败/挑最快一次。
修复必须新 source/protocol version 和新 batch root，原失败不重标通过。

## 正确性、汇总与可复现产品

每个 attempt 的 wait 后审核：exit0、demo_passed、四轨迹 gate、25 项输入 before/after
一致、全部 checksum/输出清单、null/valid/reason/evidence、counts/support、独立 CP3
auditor（复用原四轨迹 case audit）通过；同批次 canonical/summary equality 通过。
审核在计时外，报告其 command/exit/hash；child 内既有 oracle/error 计算仍在计时内。
运行前后输入不变；任一数值/QC/identity/完整性失败使批次 FAIL，不能发布成功性能结论。

发布每次 wall_ns/wall_s（含失败）、exit、correctness，以及成功五次 median/min/max。
median 定义排序后第 3 项；min/max 为同批五项端点，不丢 outlier。
如报告 samples/s，逐次由同一次 wall_s 计算，再给五次 rate 的 median/min/max；
不能混用 `N / mean(wall_s)` 的不同统计定义。五次重复不作总体置信区间推断。
没有无来源速度目标，CP3 判据是正确性、预定执行完整、可复算和可追溯。

目标产物：冻结 PROTOCOL、runner；新批次 `environment.json`、`attempts.json`、
逐次 logs/commands/checks、六个完整 Demo roots、全产品 SHA256SUMS（排除自身）；
`benchmarks/demo/REPORT.md` 引用批次/source/input/lock/环境，定义全部公开性能数字，
附从原始 attempts 重算命令。REPRODUCE 记录 setup/run/audit/recompute。
各产品是 benchmark evidence，不定义新的公共传感器/指标 schema。
README/技术报告引用同一批次，未执行的平台不填数；Windows/Linux 分别报告。

CP3 前待定：实际机器、正式 source lock、新批次名、runner/审核命令的实测形式。
输入、默认 1 warmup+5 timed、端到端范围和失败保留规则已在 CP0 明确。
只有可靠隔离且验证后才启用可选 compute_s；其缺失不阻断必需端到端 benchmark。
