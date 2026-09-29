# KineIMU Shoulder — M6.5 / CP5 发布候选验收报告

2026-09-28。版本 `0.1.0`，维护者已批准 MIT/CC0、作者 Hongbo Liao 及发布目标。
验收源码锁：`e55d68b537987f4a2cc2ac6d2ad58e15e077ed15`。
结论由本目录 `acceptance.json` 的实际 gate 记录及后续 committed proof 判定；
M6 本地软件验收与公开发布分别记录。本次没有连接设备或读取外部传感器数据。

## 独立环境与复现

从本地已提交 Git 仓库执行 `git clone --no-hardlinks --branch main`，没有拷贝
工作区、原 `.venv` 或本机缺失的资源。保留完整提交历史/Git 元数据；不是 worktree，
也不是 wheel-only demo。`clone-preflight.json` 记录新克隆最初完全干净、无 `.venv`、
无 Git alternates、sample 与源路径不是同一文件，以及新 uv cache 原先不存在。
本地克隆没有验证尚未公开的 GitHub 地址可用性。

CPython 3.12.14、uv 0.12.5；实际包从克隆路径 import，`.venv` 的
`include-system-site-packages=false`。清除外部 M1 root、PYTHONPATH/PYTHONHOME、
现有 venv/项目环境覆盖，线程变量三项为1。网络下载仅用于安装锁定的依赖，
不获取外部录制或在线生成示例。所有实际 argv/cwd/UTC/exit/日志 hash 独立留证。

从新克隆根执行 README 原命令（实际 uv 用已核验的绝对路径调用）：

```powershell
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
uv run --frozen python examples/m6_demo.py --output demo-output-02
uv run --frozen python examples/m6_demo.py --help
uv sync --all-extras --frozen
uv run --frozen pytest -ra --basetemp <new-external-test-root> --junitxml <new-evidence-file>
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen python scripts/check_docs_consistency.py
git diff --check
uv build --out-dir <new-build-root>
```

验收原克隆及输出保留于
`<temporary-workspace>/kineimu-m6-cp5-20260928-01/`。
仓库内 `run1`、`run2` 为逐字节核验的独立证据副本，非重跑产物。
复现时另选全新的 clone、cache、test temp 与输出根；不得重用这些已消费路径。

## Demo、数值及确定性

两条实际命令 exit0，每次完整四轨迹、八流、17,208 node-samples/4,304 packets；
每轨迹三次有效动作、无 missed/false，relative/proxy/recall coverage=1。
既有 CP2 独立 auditor 每次检查27,160个误差标量；packet/QC/SI、校准、AHRS、
显式 alignment/clock/heading/grid、M3/M4、thorax proxy 和原 gate 全部通过。
默认源是 synthetic，`anatomical_eligible=false`，没有精确姿态替代传感器链路。

两次各26文件；两层 checksum 独立校验。全部22 replay canonical products、
内部索引、summary 和其余24项顶层 hash 相同。两次 run.json 仅有冻结契约允许的
output/command output arg/UTC/duration/PID 变化，其余字段全部相等。

对原 CP2 锁的21个科学产物（20 case文件+report）逐字节一致。
summary 除明示的 source HEAD 单次替换外完全相同；两个命令的 Python 别名经
samefile/resolve 证明为同一可执行文件。跨锁源码 hash 差异只有既有 summary.py
CRLF/Git LF，manifest/index/run 派生 hash 均据实保留。两项 red→green 回归负控制
拒绝单位、额外说明、不同脚本/可执行文件和多余参数变化；不放宽同锁 CP2 白名单。
原失败比较和记录冲突均保留。44个实际运行 source/contract/audit 字节与候选 Git
完全一致，另有验证过成员 hash 的 runtime source ZIP。原始sample全部成员前后不变。

## 完整检查与历史证据

| 检查 | 本次结果与范围 |
|---|---|
| Fresh clone pytest | 879 collected；877 passed、2 expected skips、0 failed/errors；原完整 JUnit 和 -ra 日志保留 |
| 两项 skip | `tests/integration/test_m2_replay_m1_bench.py` 的 A/B 外部30分钟bench重放；原因：未设置 KINEIMU_M1_RAW_ROOT；不是Demo skip |
| CP4 maintainer回归 | 历史879 passed/0 skips，有真实外部M1输入；与本次hardware-free回归分列、不冒称本次执行 |
| Clone Ruff / strict mypy | exit0；mypy33个package source |
| Clone docs / whitespace | 256个tracked-clone Markdown、39不可变archive hash、0errors；exit0。工作仓库更多历史scratch文档不属于克隆 |
| Clone build / archive | pinned sdist→wheel成功；34 source/typing和57 notice files、许可/作者/版本/依赖/README及排除范围核验通过 |
| 新归档独立安装 | 另建wheel/sdist两个venv，锁定hash依赖；8条实际命令全部exit0；外部cwd、-I分析API/metadata/notices通过 |
| 既有证据完整性 | CP4 delivery248文件、CP3 frozen556、installed52+upstream2许可原文、66旧制品/notice文件hash核验通过 |
| CFF/授权 | 克隆CFF/完整MIT/CC0及notice字节与已通过CP4官方schema/授权审核的锁一致；没有更改身份或发布日期 |
| 本次新增工具/文档 | 单独root Ruff/docs/whitespace验收记录；provenance与dynamic docs回归；全部失败原记录保留 |

完整877+2回归使用冻结克隆ref。其后收口唯一既有代码修改是文档检查器：
CURRENT_TASK不再强制早已完成的M1根因/bench禁令，而要求项目名、HEAD、Exact next action。
两项回归先RED，随后与原docs integration及两项provenance控制一起复验。
数值/生产package代码和测试输入不变；该工具不进入wheel/sdist或分析链路。

没有新的 benchmark 测量或实时吞吐声明。已有每个性能数字仍由
[CP3冻结协议/原始记录](../../benchmarks/demo/REPORT.md)及556文件完整性绑定。
硬件/生产算法/公开schema/门限/依赖/原输入及旧证据不变；不重新采集。

## 制品与版本

本次clone-build-02两件归档从上述源码锁、Git LF字节独立重建；归档审核和安装
均针对同一hash，副本逐字节相同。这些是CP5验证制品，不覆盖CP4 candidate02。
其与CP4归档的成员差异仅summary.py既有CRLF/LF和wheel RECORD，证明见artifact-copy-02.json。
以下SHA-256不代表tag/上传，也不把后续收口文档提交冒充构建源码锁。

| 本次制品 | bytes | SHA-256 |
|---|---:|---|
| `kineimu_shoulder-0.1.0-py3-none-any.whl` | 292823 | `2aab10f79a0943cffe5cbccc2e749171c95f4219865d8cf16b37f21d95df99fb` |
| `kineimu_shoulder-0.1.0.tar.gz` | 221443 | `16fc956e210b6cf58f982529a88acef0c62dbebe5a083cc8415fe41547fefee3` |

CP4原许可候选仍保留：[candidate02](../M6_CP4_FINAL_20260928/README.md)。
原wheel SHA-256 `4ea9adec9098c6f62315279b4189c3755de83e48fed02a0fb6259b544148c278`；
原sdist `8f317668585f99d59cd9e6b263180b5947d9404bf58b0357f47cb764858782f7`。
初版package版本是0.1.0；V1软件验收完成不改述成已发布版本1.0。

## 验收边界与交付

[R01–R22覆盖](COVERAGE.md)逐项绑定证据；失败及纠正见[ATTEMPTS](ATTEMPTS.md)。
Linux NOT RUN；CI配置不算实际Linux结果。Windows同平台确定性不等同跨平台相等。
静态重力不确定完整heading；known alignment/clock/heading为合成构造假设。
真实M1肩部指标缺支持证据仍null/invalid；无人体/临床、GL/scapular精度或风险/结局评分。
电池/外壳/佩戴、人体/动捕/临床验证继续处于V1之外。

公开目标已批准，但本次没有创建公开仓库、改变origin、push、tag、GitHub Release
或PyPI上传；没有删除、迁移或改写旧历史/大证据。后续公开发布及完整历史/firmware
材料分发仍需对应授权/许可审查。本地软件候选验收可以独立完成。
交付快照及其后commit proof绑定当前证据/文档；动态状态和后置proof不纳入自身hash，
避免循环。准确执行/交付/收口HEAD分开记录；下一动作是按维护者后续明确范围推进。
