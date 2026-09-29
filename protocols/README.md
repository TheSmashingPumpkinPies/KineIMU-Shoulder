# 实验规程

当前规范入口：

- [硬件与采集基线](../HARDWARE_PROFILE.md)
- [佩戴与重复佩戴](../MOUNTING_PROTOCOL.md)
- [视频/IMU 同步](../SYNC_PROTOCOL.md)
- [M1 采集契约 v0.1](M1_ACQUISITION_CONTRACT.md)
- [M1 时间与丢包预算 v0.1](M1_TIMING_BUDGET.md)
- [M1 刚性 fixture 时钟映射 pilot](M1_CLOCK_MAPPING_FIXTURE.md)
- [验证计划](../VALIDATION_PLAN.md)
- [数据治理](../DATA_GOVERNANCE.md)
- [结果复现](../REPRODUCIBILITY.md)

M1 会话清单的机器可读 schema 与合成示例分别位于 `schemas/` 和 `examples/`。
遥测包参考编解码器位于 `kineimu_shoulder/io/m1_packet.py`；identity/config、
clock exchange 与 status 控制面参考编解码器位于 `kineimu_shoulder/io/m1_control.py`。
主机端 `.kimu` 有界 framing/parser 位于 `kineimu_shoulder/io/m1_capture.py`；
不修改原始记录的包/样本序列与设备时间戳 QC 位于 `kineimu_shoulder/io/m1_qc.py`。
Node A 的 USB-C CDC v1 staging recorder 位于 `scripts/capture_m1_usb.py`：它把完整的
USB 字节流保存为 `.usb.bin`，跳过启动诊断前导后验证 v1 packet，并把合法 payload 写入
冻结的 `.kimu` 外层 framing；无效 header、CRC/解码错误、截断尾部和诊断字节均通过
`.events.ndjson` 保留，不做静默修复、丢弃、单位换算或重采样。安装方式为
`uv sync --all-extras --frozen`。固件 BLE GATT 服务的 buildable acquisition slice
位于 `firmware/xiao_nrf52840_sense/m1_ble/`，实现本契约的 identity/config、clock
exchange、telemetry notify 和 status characteristic；主机 BLE central/recorder
位于 `kineimu_shoulder/io/m1_ble.py`，可执行入口是 `scripts/capture_m1_ble.py`，使用
显式 A/B 地址并在开启 telemetry 前读取/校验 identity/config、MTU 和 status。物理 BLE
互操作、持续时序/丢包与双节点同步仍未验收。USB-C 路径只用于单 Node A 短采集，不能
替代 M1 BLE 验收。
后续在此编写逐步操作 SOP，引用上述规范，记录 protocol 版本、条件、重复次数、参考方法和输出位置。
