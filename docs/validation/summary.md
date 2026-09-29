# M5.5 / CP5 — KineIMU Shoulder 验收总报告

日期：2026-09-28（Asia/Shanghai）。入口 `main@aba175f1`。
**CP5 PASS；M5 DONE 于冻结 synthetic/replay 范围。** 机器判定 (complete record retained in the local evidence archive)。
本报告汇集 CP0–CP4 的既有验收证据；本目录最终
checks.json (complete record retained in the local evidence archive) 和 evidence-audit.json (complete record retained in the local evidence archive) 给出实际结果。
不重新运行、修改或重分类任何既有 formal 根。

交付入口：[要求—用例—证据索引](coverage.md)、
[复现命令](reproduce.md)、限制、覆盖缺口与 M6 输入 (complete record retained in the local evidence archive)。
机器索引 evidence-index.json (complete record retained in the local evidence archive) 展开两次保留运行的逐文件 SHA-256，
并指向每个 checkpoint 的配置、代码锁、输入、独立审计及失败历史。
这些是 validation-only 文档和索引，不改变公共采集 schema。

## 判定边界

M5 验收要求的四个条款均有对应证据；详见覆盖矩阵。有效判定限于
冻结有限设计内的 synthetic 数值与 evidence gate，以及 recorded replay
的完整性、确定性、质量处理和缺证据拒绝。所有记录的肩部指标仍
null/invalid；没有物理解剖、人体、临床或 glenohumeral/scapular 验证。
M0 保持 DONE，硬件保持冻结；M6 demo/release 尚未验收。

| Checkpoint | 已接受范围与结果 | 精确代码锁 / 证据入口 |
|---|---|---|
| CP0 | 输入层、独立参考、门限、种子、coverage 和严格报告/退出契约已冻结；不是数值运行 | `4eb5d9e1735cd27843c48cfeba3c12d1ae2607db`；CP0 审查 (complete record retained in the local evidence archive)；contract `e8a76451…`，truth `1cd431c6…` |
| CP1 | 源工具/oracle；两个独立进程各 37 文件一致；4 个 Q demo，不运行 AHRS | `ee0741334e430c7cf8b5b9845d0a9b48426fecad`；源工具报告 (complete record retained in the local evidence archive) |
| CP2 | 30 个 CLEAN E/S/Q 用例、2 项比较；180 eligible reps，0 missed/false；相对时长 coverage 均 1；各 131 文件一致 | `92d06d0589689417162eb80d351566045c7c25b7`；基线报告及误差表 (complete record retained in the local evidence archive) |
| CP3 | processing/1.1 的全部 1,142 用例，0 failed/not-run；589 W 用例 relative coverage/recall 均 1、0 missed/false；各 5,380 canonical 文件一致 | `01c4e23bd82bcbec6ae775bf6db6c67471fa6ac3`；完整再验收 (complete record retained in the local evidence archive) |
| CP4 | 两次完整 B/C/ADR-011 D 回放，35 canonical 产品及外层 checksum 一致；六项独立数值审计通过；原始输入前后不变 | 数值 `a72bdd18dd3567bb3b043c4cd6c75b16b7311cf9`，审计 `fbcb118ba5eaf54c739767ac36ac9bdb129ad3e5`；正式回放验收 (complete record retained in the local evidence archive) |

CP2 的逐用例 max/RMSE、单位、原门限、独立标签和实际/期望/signed/absolute
数组保留在 `retry1/run{1,2}/report.json` 及对应 errors/result 文件；总报告
不以一个聚合最大值替代每条门限。CP3 保留所有有限种子和每个 session
的误差与分母，297 stress 用例完成只说明局限被记录，不计为 accuracy PASS。
33 C、589 W、297 stress、122 evidence、67 boundary、34 rejection 合计 1,142。
CP3 两次运行各独立重算 13,844,981 error scalars；CP2 各 451,090。
这些是验证工作量与数值误差证据，不是运行性能 benchmark。

CP4 每次 B 读取完整 4 条 Q/8 节点，共 17,208 原始行、4,304 包；
C 读取完整 Node B 832 行/208 包；D 读取 A 187,772 行/46,943 包、
B 191,424 行/47,856 包，共 379,196 行/94,799 包。
B index 23,297 原削顶/超量程行保持 null 与两个原 reason；其余 379,195
节点四元数及三次独立初始化世界已核验，不跨世界组合。
187,772 行下游诊断均保留缺 timing/heading/alignment 的不可用结果。

## 版本、失败与来源

- CP2 使用当时的处理锁；CP3 按已接受
  [ADR-010](../adr/ADR-010-explicit-short-gap-reconstruction.md)
  引入显式、重力支持的短缺口重建。旧 CP2 结果没有被标成 processing/1.1；
  新 CP3 的 CLEAN 控制覆盖新路径，旧 46 个失败全部在完整再验收中解决。
- 真实 D 按已接受
  [ADR-011](../adr/ADR-011-recorded-quality-segments.md)
  分段，保留拒绝行并重启原 AHRS；不补造共同时间/航向或解剖对齐。
- [CP2 partial](../PUBLIC_AUDIT.md)、
  旧 CP3 失败 (complete record retained in the local evidence archive)、
  原 D 失败 (complete record retained in the local evidence archive)、
  E1 失败 (complete record retained in the local evidence archive)、E2 原 PID 审计失败和
  E3 原 Git EOL 审计失败全部保持原状。E4 接受的是同一完整 E2 数值对，
  不是对旧失败报告改写 PASS。
- CP3 source ZIP 保留 86 项精确运行源码；CP4 source ZIP 保留 63 项，
  tool ZIP 单独保留。仅原 CP4 两个已声明 path/hash 对允许 Git LF 与
  runtime CRLF 的身份映射，见
  [绑定说明](../PUBLIC_AUDIT.md)。不对保留源码做规范化。
- CP4 证据提交 `10a51ae69f6ac258bd9543f4d6551cb623424431`；CP3 证据提交
  `739714f3d0363478f78bf94ef5ece58bd9071371`。CP5 是其后的收口证据，
  不改变原数值锁。exact CP5 提交按 REPRODUCE 中的 Git 命令解析。

## CP5 放行清单

最终结果由本目录 Verification 段记录：完整 pytest 必须实际设置外部 M1 根，
两项外部测试不得 skip；审计 guard、Ruff、strict mypy、docs 和 whitespace
全部 exit 0。另核对保留两次运行的完整文件清单与既有独立 hash map、
冻结 contract/truth/case-manifest、运行配置/代码/依赖锁的来源索引、
CP4 原始输入快照及原失败证据。没有新增生产/数值算法，因此没有新的
数值门限或算法测试义务；既有 tests 与正式数值证据仍必须通过。

硬件/固件构建本段不适用：没有固件、硬件或采集代码更改，reference-board
build 继续引用 M1 留存证据。M6 LICENSE/CITATION、clean-clone demo、完整
release benchmark 尚需独立完成，不由 CP5 通过代替。

## Verification — CP5 PASS

| 检查 | 新执行结果 |
|---|---|
| 完整 pytest，实际外部 M1 根 | **762 passed，0 skipped，exit 0**；包括两项外部 M1 测试 |
| 独立审计回归 | E3 worker guard 4 passed；最终 E4 source/worker guard **8 passed**，均 exit 0 |
| Ruff / strict mypy | exit 0；mypy 检查 32 个源文件 |
| docs / whitespace | docs 1,235 Markdown / 39 immutable archive hashes / 0 errors；`git diff --check` exit 0 |
| package build | 固定 uv 0.12.5，sdist 与 wheel 构建 exit 0；不是 M6 release 放行 |
| 保留证据完整性 | 11,302 仓库文件，CP1–CP4 八个完整根；外部 11 项 + manifest；CP3/CP4 runtime 86/63 与 tool 4 个 ZIP 成员；均匹配 |
| 分层验收核对 | 全 1,142 行分类 CSV 对齐；589 W 同时 accuracy/coverage/recall/count 通过；其余按冻结类别判断 |
| 只读复现/误 hash 控制 | 文档原代码 exit 0；内存中的错误期望 hash 被拒绝，原始文件不变 |

操作日志按本目录 `.gitattributes` 保留实际字节；其 SHA-256 由 checks.json
记录；日志专属 whitespace 属性识别 CRLF 行尾，仍检查实际空白错误。
初次 staged whitespace 把原日志 CR 误判尾随空白，保留该输出并按此属性重新
检查通过，未修改日志字节。JSON 索引为 UTF-8/LF。初次包构建因 `uv.exe` 不在 PATH 而未启动，
随后定位固定版本并成功执行；NOT STARTED 记录与成功结果分别保留。
收口辅助断言曾错误要求压力/负例数值 gate 全部通过；修正为冻结类别的
`passed` 判定，并单独核对全部 W 数值/分母 gate，未改原结果或门限。

没有未解决的必需 M5 工作域失败，也没有以 skip、全部拒绝或修改原始数据
取得通过。全部范围限制和 M6 尚待完成事项在 M6_HANDOFF.md。
