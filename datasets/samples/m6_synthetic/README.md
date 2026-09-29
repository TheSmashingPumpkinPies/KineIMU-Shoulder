# KineIMU Shoulder — synthetic stored-Q sample

**INTERNAL ONLY / public redistribution pending.** 数据许可尚未由维护者决定；
本地 CP1 输入放行不授予公开分发许可。四条轨迹均为 synthetic，
不含人体采集、视频或个人数据，不代表解剖、临床或诊断验证。

按 [M6 Demo 契约](../../../docs/M6_DEMO_CONTRACT.md) §1，选取
原 [M5 CP1 run1](../../../docs/validation/sample-provenance.md) 的
25 个必要文件，逐字节复制，合计 **4,539,058 bytes**。
来源、逐文件大小和 SHA-256、生成源码 hash、配置引用及未分发成员见
[provenance.json](provenance.json)。本目录不是原 run1 的完整副本。

| 顺序 / ID | 运动与侧别 | 节点 | 每节点包 / 样本 |
|---|---|---|---|
| F90 | flexion / left | A thorax、B humerus | 538 / 2,151 |
| AL90 | abduction / left | 同上 | 538 / 2,151 |
| AR90 | abduction / right | 同上 | 538 / 2,151 |
| T-MIX | flexion / left，移动 thorax | 同上 | 538 / 2,151 |

8 个流合计 4,304 包 / 17,208 node-samples；capture 合计 585,136 bytes。
100 Hz 合成输入的 device time 为 0–21,500,000 us；分析窗口 5–21.5 s，
segmentation context 使用完整 0–21.5 s。每条动作独立标注三次完整重复。
这些是输入定义和规模，不是处理性能或真实硬件 104 Hz ODR 的测量。

`.kimu` 是唯一传感器观测：synthetic 量化整数、原始 counter 与 timestamp。
每轨迹 `A-si.json` / `B-si.json` 为保留的独立 pre-Q SI 参考；
`metadata.json` 记录 R_NS、R_NK、已知初始 q_WN、校准和构造时钟。
`annotations.json` 保留独立 motion / nominal M4 / summary 标注；
`observation-labels.json` 保留观测标签；`case-manifest.json` 中对应
`<ID>/CLEAN-Q/SAME/0` 配置。参考和标注不是传感器观测。
`manifest.json` 保留历史 CP1 source-tool 状态，不改写为 M6 验收结果。

生成源码锁：`ee0741334e430c7cf8b5b9845d0a9b48426fecad`；
原 CP1 数据交付锁：`1e174f265daa6d09896683013d3c5f50a6da271f`。
生成依赖版本和 source hashes 保留于 manifest 与 provenance；
不在运行时重新生成、补写、去重或规范化输入。

内部 SI：加速度 m/s²、角速度 rad/s、角度 rad、时间整数 us、单位 quaternion。
原配置与标注中 `peak_deg` 等 `_deg` 字段保留度，`_s` 字段保留秒；
不改变原字段单位或将它们当作统一 SI 数值重新解释。
姿态采用 active scalar-first Hamilton `wxyz`、右手列向量；R_AB 映射 B→A。
显式转换为 sensor → R_NS node → AHRS q_WN → R_NK segment → common world。
thorax +X anterior / +Y left / +Z superior；humerus +Z proximal。
已知共享 world、initial heading 和 identity calibration 是合成构造的
Assumed / Experimental 条件，`anatomical_eligible=false`；静态重力不能确定完整 heading。
输出语义仅限 humerothoracic approximation，不推断 glenohumeral、scapular 或临床指标。

[SHA256SUMS.json](SHA256SUMS.json) 保持原 36 个成员的完整字节，map 自身 SHA-256 为
`2aa180e32003f91e57accf1d53c5b4b914e0c9e9c0ab4cdb22db02a3ab0964f9`。
本目录提供其中 24 个成员与 map；12 个未分发成员逐项列于 provenance：
每轨迹的 `A.bin`、`B.bin`、`exact-orientations.json`。
它们不是既有 stored-Q loader 的必要输入，不应要求 sample 包含全部 36 个成员。
本目录 `.gitattributes` 禁止 JSON/capture 的 Git 文本转换以保留 hash。

从仓库 clone 根目录审核输入（无需设备或外部 raw root）：

```powershell
uv run --frozen python -c "from pathlib import Path; from kineimu_shoulder.validation.stored_demo import input_audit; print(input_audit(Path('datasets/samples/m6_synthetic')))"
uv run --frozen pytest tests/integration/test_m6_sample.py
```

审核只读；缺文件抛 FileNotFoundError，map 篡改或成员 hash 失配抛 ValueError。
原 map 由独立固定 hash 锚定，重算篡改成员的 hash 不能绕过审核。
`run_stored` 在处理前拒绝四种 ID 之外的轨迹。
M6 一次命令完整演示是后续 CP2 交付；本目录当前只交付输入。
