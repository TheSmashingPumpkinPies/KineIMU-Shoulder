# M1 独立 FIFO/队列压力与 BLE 断连恢复实验计划

预声明日期：2026-09-15（Asia/Shanghai）
实验范围：M1 BLE 传输工程测试；不是正式 30 分钟验收，也不与其共享任何
raw 数据集。
固件：使用当前已在两块板上运行的四槽异步 TX 实验固件；实验期间不刷写、
不修改固件、协议、阈值或公共 schema。

## 固定对象与前置条件

- Node A = thorax，Node B = upper_arm；使用已登记的硬件 ID、BLE 地址和 COM
  端口，不以发现顺序或 COM 顺序分配角色。
- 两个节点必须分别通过 identity/config、硬件 ID、firmware Git commit、配置代、
  clock epoch、104 Hz ODR、±4 g、±500 dps、四样本 batch 和 ATT MTU ≥127 的检查。
- 3 次 clock exchange 在每条连接上完成；设备时钟时间和 host monotonic 到达时间
  分开保存。
- CDC 原始字节在 BLE 控制开始前打开并持续到 teardown；BLE `.kimu` 和 BLE
  transport-event sidecar 由既有 recorder append-only 写入。
- 所有输出位于本次新建的外部目录；A、B 两项测试各自有独立 raw 子目录和
  session ID，均不写入 `datasets/`，不覆盖历史 `<external-data>` 目录。
- 正式 `protocols/M1_TIMING_BUDGET.md` 的阈值在本实验前冻结；实验结果不能
  反向修改或重解释该阈值。

## 测试 A：FIFO/队列压力

### 施压方法与持续时间

在两个节点同时进入 stable streaming 后运行 90 s。保持传感器静止，配置仍为
104 Hz 采样、四样本/notification、ATT MTU 127。实验驱动器在 host 的每个
telemetry callback 调用 recorder 前固定阻塞 8 ms；只延迟 callback，不丢弃、
不篡改、不过滤 payload。这是预先声明的 host-consumer 压力刺激，用于增加 BLE
发送、固定四槽 TX queue 和上游 acquisition queue 的真实排队压力。CDC 线程
不做延迟和解析，只保存精确字节。

### 预计观察量

- 每节点名义上约 `90 × 104 = 9,360` 个已采集样本和约 `9,360 / 4 = 2,340`
  个完整四样本 packet；实际 raw 接收量、device status 累计量和差值全部报告。
- 记录每个节点 sensor FIFO overrun、firmware acquisition queue overrun、
  `samples_dropped_before_packetization`、TX enqueue/disconnect/stop drop、
  notify failure、`transport_backpressure_events`。
- 记录 sensor FIFO/packet flag、acquisition queue status 字段、TX queue high-water、
  CDC `tx_queue_high_water` 以及所有 trace snapshots；每一个 packet/sample
  sequence gap 都保留 previous/current/missing_count/stream offset/connection。
- 记录 raw decode/CRC/framing、duplicate/reorder、timestamp 和 epoch 结果，以及
  status delta 与 raw packet/sample 数的 reconciliation。

### 归因规则

- packet/sample gap 只能在 status counter、CDC trace、packet flag 和 event sidecar
  共同闭合时归因；不能仅凭 host 到达时间把 loss 归为 BLE。
- TX enqueue/disconnect/stop drop 和 notify failure 归入 transport-backpressure
  类；firmware queue overrun 与 pre-packetization drop 归入 acquisition-queue
  类；sensor FIFO overrun 只能由 FIFO status/packet flag/status counter 归入。
- raw 中的 decode/framing 或 CRC 错误属于 host capture/协议完整性类，不得伪装成
  device queue loss。
- 任一 sequence gap 不能由上述证据闭合时，标记 `unattributed`，A 测试不声称
  “全部损失可归因”；不修复 raw。

## 测试 B：BLE 断连恢复

### 施压方法与持续时间

在双节点 stable streaming 后运行 55 s，不施加 host callback 延迟。实验驱动器
按绝对的 streaming-relative schedule 主动断开并保持重连阻塞：

| 节点 | 断开时刻 | 保持不可用 | 目的 |
|---|---:|---:|---|
| B | +15.0 s | 3.0 s | 首个断连/恢复 |
| A | +35.0 s | 3.0 s | 第二个独立断连/恢复 |

recorder 的既有状态机负责重新连接。每个断开都记录 stimulus request/return、
recorder `disconnect`、重连成功的 `reconnect`、配置重读、clock exchange、
telemetry 恢复，以及所有重连尝试。两次恢复从断开事件开始均以 10 s 为硬目标；
`reconnect` 后的 identity/config read 必须在该窗口内完成且通过。

### 预计观察量

- 每节点总名义采集量约 `55 × 104 = 5,720` samples、约 `1,430` packets；
  raw 可用量会排除 BLE 不可用区间，device status/CDC 用于解释差值。
- 对 A、B 各记录 `disconnect_host_monotonic_ns`、`reconnect_host_monotonic_ns`、
  identity/config revalidation 时间、telemetry resume 时间；报告 link-unavailable
  和 telemetry-unavailable 两种区间。
- 列出断连前后全部 packet/sample sequence gaps、缺失数量、packet flags、status
  counter delta、CDC acquisition/TX trace，并分别报告不可用区间内的缺失 packet
  与 sample。

### epoch/map 决策

只有同时满足以下证据才保留同一 device clock epoch：重连后的硬件 ID、boot ID、
firmware/config signature、clock epoch 完全一致；无 fatal/reset；raw 的前后
序列/时间戳单调；状态累计计数与 gap/CDC loss 解释一致；且没有额外无法归因的
epoch 变化。即便保留 epoch，BLE outage 内的数据仍标为 unavailable，不插值。

任一条件失败时，raw 原样保留；报告为在断连边界开启新的处理 epoch/map，禁止跨
边界拟合或补点。新 map 是 processed/report 元数据，不改 raw packet 内的 epoch。

## 观测缺口与最小复现

当前 firmware `main.c` 把 status 的
`acquisition_buffer_high_water_samples` 明确写成 `0U`，而
`sample_queue.c` 维护的实际 `high_water_samples` 没有接入 BLE status 或 CDC
trace。实验会原样记录 status 的 0，并把该字段标为“不可观测/非实测高水位”；
若同时出现 queue overrun，则保留一条 source-line 最小复现。这个缺陷只报告，
本实验不修复。

## immutable artifact 与分析

每项测试保留：预声明计划副本、run config/control log、两个 CDC byte capture
及其 decoded log、两个 BLE `.kimu`、两个 `.events.ndjson`、`session.json`、
独立 offline audit、完整 sequence-gap 列表和 `SHA256SUMS.txt`。分析程序只读
打开 raw；先后 hash 必须相同。任何失败、不完整连接或未归因 loss 都按事实报告，
不通过删数据、插值、重采样或事后调阈值改善结果。
