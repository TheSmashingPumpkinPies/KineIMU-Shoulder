# M6 Release Checklist — KineIMU Shoulder

## Curated repository status — 2026-09-29

The maintainer has created the separate KineIMU-Shoulder repository. Its curated
candidate is checked independently in [PUBLIC_VERIFICATION](PUBLIC_VERIFICATION.md).
Additional data authorization remains pending; no candidate upload, tag, Release
or PyPI publication has occurred. The dated M6 acceptance below describes the
original source tree, rather than acceptance of the current export.

## Current release-review state — 2026-09-28

M6 **CP0–CP5 PASS; local V1 acceptance DONE**.
Fresh clone/cache/venv, two complete demos and independent audit, full877+2
expected external-data skips, static/docs/build/archive/two installs all pass.
[CP5 coverage](../experiments/M6_CP5_20260928/COVERAGE.md) binds all R01–R22;
[CP5 candidate report](../experiments/M6_CP5_20260928/REPORT.md) separates local
acceptance from publication. Linux NOT RUN; actual public publication deferred.
Maintainer approved all listed documentation/license/author/version/repository decisions.
Current [README](../README.md), [technical report](M6_TECHNICAL_REPORT.md),
[notice inventory](../THIRD_PARTY_NOTICES.md) and
[review decisions](release/REVIEW.md) are the CP4 review deliverables.
Actual build/install/check records are in
[M6_CP4_FINAL_20260928](../experiments/M6_CP4_FINAL_20260928/README.md).
[ADR-012](adr/ADR-012-release-documentation-and-license-selection.md) records
approved English README / Chinese report, introduction, MIT selection,
CC0 original sample permission, copyright holder Hongbo Liao and first version
0.1.0. Year2026, citation author Hongbo Liao and public owner TheSmashingPumpkinPies
were then explicitly accepted. Full MIT/CFF/package metadata are recorded;
CFF schema, documentation, full879 regression, build/archive and independent installs PASS.
Old internal previews are retained separately and are not relabeled.

| Requirements | Current evidence / remaining gate |
|---|---|
| R01 clean clone | CP5 OPEN; independent package installs do not replace a fresh-clone demo |
| R02/R10/R20/R21 demo, reproducibility, outputs and path safety | [CP2 PASS](../experiments/M6_CP2_20260928/README.md); final clone/ref checks remain CP5 |
| R03–R09/R13 docs, architecture, hardware, protocols, methods, validation and limits | README/report/navigation consistent; CP4 links/archive checks PASS; fresh-clone commands passed CP5 |
| R11 sample | [CP1 PASS](../experiments/M6_CP1_20260928/README.md) for input identity; current CC0 permission approved in sample annex; original historical labels unchanged |
| R12 benchmark | [CP3 PASS](../benchmarks/demo/REPORT.md), locked protocol/attempts/recompute and committed-byte proof |
| R14 project license | Full MIT notice: Copyright (c) 2026 Hongbo Liao; final archive inclusion PASS |
| R15 citation | Approved author/title/version/MIT/repository destination; full official schema check PASS |
| R16 third parties | Installed texts and two version-tag references retained; Python artifact notices checked; firmware binary/platform review remains distribution-specific |
| R17 artifacts | Licensed `0.1.0` candidate02; fresh build/archive/independent installs PASS |
| R18 required checks | CP4 full879/0 skips, Ruff, strict mypy33, docs/whitespace PASS; CP5 fresh-clone877+2 expected skips passed separately |
| R19 platform | Windows checks recorded; Linux NOT RUN |
| R22 publication | Public destination approved; actual repository creation/publishing and large evidence distribution deferred |

The following original CP0 freeze remains the requirement definition and historical
baseline; its then-OPEN statuses and then-future file names are not current progress.

## Historical CP0 requirement freeze

2026-09-28 / M6.0 CP0 requirement freeze。M6 checkpoint 与 M5 同名 CP 分开。
本清单将 [ACCEPTANCE_CRITERIA 的 M6](../ACCEPTANCE_CRITERIA.md) 每项交付映射到
归属阶段、可观察判据及证据路径；也映射 [M6 计划](../M6_DEVELOPMENT_PLAN.md)
要求的完整处理/边界/独立验收。规格放行不能替代运行、性能或发布验收。

状态：**CP0 PASS（规格放行）；CP1–CP5 OPEN**。本段盘点、逐项规格审查及
documentation/whitespace 检查见 [checks.json](../experiments/M6_CP0_20260928/checks.json)。
下表的证据路径若尚不存在，均是目标
位置而不是已完成证据。已存在证据只用 Markdown 链接，未来文件名用代码文字。
每个后续 checkpoint 保留实际 commands/exits/logs、source/input/config/lock hashes
及失败 roots；更新本清单状态时不改写旧证据。

## 要求到阶段和证据的完整映射

| ID / M6 要求 | 归属及依赖 | 可观察通过判据 | 目标证据 / 当前状态 |
|---|---|---|---|
| R01 clean clone | CP2 → CP5 | fresh clone/ref + fresh venv，按 README 安装/run；无 PYTHONPATH、外部 M1 root、本机文件补拷或设备；完整成功 | CP5 clone/env/commands/checks/source hashes；OPEN |
| R02 至少一个完整 replay/synthetic demo | CP0 → CP1 → CP2 → CP5 | 默认四轨迹 stored-Q、八流完整执行；所有阶段与原 numerical gates 有证据；一次运行命令 exit0 | `examples/m6_demo.py`、`docs/M6_DEMO.md`，CP2 四 cases/独立 audit；OPEN |
| R03 README | CP2 → CP4 → CP5 | final naming、clone/ref/安装/运行/输出、synthetic 限制、已实测平台；commands 在 fresh clone 实测 | README diff/链接检查、CP5 transcript；OPEN |
| R04 architecture | CP4 → CP5 | 正确连接现有 pipeline、production/validation、transform/timing、input backend；不声称不存在 API | ARCHITECTURE 与技术导航审查/一致性记录；OPEN |
| R05 hardware documentation | CP4 → CP5 | reference board/firmware/build/M1 evidence 导航；USB PASS 与 BLE 限制分开；hardware freeze、V1 wearable 边界 | HARDWARE_PROFILE、firmware README、ADR-008/009/技术报告覆盖；OPEN |
| R06 protocol documentation | CP4 → CP5 | schema 0.1、packet/container/time、QC、clock/resampling/conventions 可定位且一致 | DATA_FORMAT、M1/M2 processing、SYNC/FRAME protocols 导航/链接记录；OPEN |
| R07 algorithm documentation | CP4 → CP5 | mature backend/version/I/O转换、calibration/AHRS/M3/M4、ADR-010 processed model、heading/drift 限制明确 | BACKEND_CONTRACTS、M2/M3/M4/M5 contracts、算法引用导航审查；OPEN |
| R08 validation documentation | CP4 → CP5 | M0–M5 evidence locks/CP5 coverage可定位；synthetic/recorded 分别陈述；旧失败不抹除 | M5 CP5 COVERAGE/index、REPRODUCE、M6_TECHNICAL_REPORT；OPEN |
| R09 limitations | CP0 → CP2 → CP4 → CP5 | summary/README/report 明示 synthetic、anatomical=false、known assumptions、非临床/GL/scapular、BLE/wearable范围；真实缺证据值保留 null | Demo contract §6、summary.md、README/技术报告审查；OPEN（规格已定义） |
| R10 reproducible examples | CP1 → CP2 → CP5 | 固定依赖/input hashes；两 fresh processes 同锁 canonical/summary equality；失败不覆写；示例不用 live acquisition | CP2 pair maps/独立审核/negative controls，CP5 clone pair；OPEN |
| R11 sample dataset | CP0 → CP1 → CP4 | 25 原字节文件、来源/units/frames/labels/license/选择成员清单；与原 map/Git 绑定、前后不变，无人体/个人数据 | `datasets/samples/m6_synthetic/README.md`/来源清单/CP1 hashes；OPEN；公开分发许可待决 |
| R12 benchmark results | CP0 draft → CP2 correctness → CP3 → CP4 | 协议先冻结；1 warmup+5 timed 预定 attempts；每次正确性/失败保留；公开每数值可由 raw重算、边界/机器完整 | [PROTOCOL_DRAFT](../benchmarks/demo/PROTOCOL_DRAFT.md) → PROTOCOL/runner/raw/REPORT/recompute；OPEN，尚无结果 |
| R13 technical report | CP3 → CP4 → CP5 | 说明问题/系统/units/frames/methods/evidence/benchmark/limitations/reproduction；无超域解释；引用原锁 | `docs/M6_TECHNICAL_REPORT.md` + coverage review；OPEN |
| R14 LICENSE | maintainer decision → CP4 → CP5 | 项目许可经明确确认，LICENSE 文本、metadata、third-party obligations 与 sample 分发一致 | LICENSE、授权记录/notice 核对；BLOCKED FOR CP4（待维护者选择） |
| R15 CITATION.cff | maintainer metadata → CP4 → CP5 | 作者/名称/引用版本/日期/identifier据实确认，CFF 解析/字段验证，仓库地址据实 | CITATION.cff、metadata 授权/validation；BLOCKED FOR CP4 |
| R16 第三方声明 | CP4 → CP5 | runtime/optional/toolchain版本/许可/算法引用区分，所需 notices 保留；不只列 import 名 | THIRD_PARTY_NOTICES.md、dependency/notice review；OPEN |
| R17 package/release candidate | CP4 → CP5 | pinned uv build、sdist/wheel完整元数据/许可/README核对，独立安装；clone demo与wheel API范围区分；候选制品hash/版本据实 | build/install logs、artifact inventory/hashes；OPEN，当前package版本0.1.0 |
| R18 required Python checks | CP2/CP3/CP4 → CP5 | pytest、Ruff、strict mypy、docs、whitespace/build actual exits；clean clone skips原因列明，Demo零skip；maintainer外部M1全回归另列 | 各段 checks/logs；CP5完整结果/skip list；OPEN（CP0仅docs/盘点） |
| R19 platform claims | CP2 → CP5 | Windows首验；Linux实际执行才可宣称支持；单平台pair与跨平台 equality分别记录 | OS/versions/CI run/ref/result；OPEN，CP0仅Windows inventory probe |
| R20 demo output/provenance | CP0 → CP2 → CP5 | 26成功文件、两层checksums完整；run.json与原M5 report状态分开；八指标unit/valid/reason/evidence/分母可读 | contract §5–6；CP2 output inventory/summary review；OPEN |
| R21 strict failure/path safety | CP0 → CP1/CP2 → CP5 | missing/hash/unsupported/已有根/unsafe path拒绝；partial根不重跑；额外repo-path guard、resolved link目标受保护；输入始终不变 | inventory guard probes + CP1/CP2 negative-control artifacts；OPEN（existing API探针已留存） |
| R22 local acceptance vs remote publication | CP5 local → final closeout | 本地M6 DONE不冒称push/tag/Release/PyPI已发布；大证据分发保存原历史/锁/hash，再独立授权同步 | M6总报告/最终HANDOFF；remote状态单列；DEFERRED，不阻断CP0 |

R01–R15 完整覆盖 M6 验收原文；R16–R22 落实计划/治理与实际依赖。
R14/R15 以及 sample 许可、最终版本/候选 ref 的决定不能用软件默认值代替。
未决项由 CP4 进入前取得明确维护者确认，CP0 不为此暂停已授权的规格冻结。

## CP0 规格放行表

| CP0 ID / 计划门 | 本段可观察证据 | 放行标准 |
|---|---|---|
| C01 每条 M6 要求有归属/判据 | R01–R22 + 本表 | 原文逐项映射无遗漏，每行阶段/证据/状态完整 |
| C02 真实可调用接口 | inventory `api`/40 exporter dependencies、contract §2–3 | import成功、签名/读写/错误/算法边界明确；未把目标CLI冒充已实现 |
| C03 fresh-output protection | inventory 13个 non-writing guard probes、contract §4 | 已有/unsafe roots拒绝行为记录；现有docs/scripts缺口明确归CP2 wrapper，不关闭原防护 |
| C04 最小input集合/identity/规模 | inventory 25逐文件bytes/hash/Git匹配、8流decode/QC、before=after | 完整实际必需成员及原map锚一致；map未分发成员边界明确；不是只读一条轨迹 |
| C05 clean clone与默认方案 | contract §1–5 | sample copy路径、analysis install、CLI/exit/output、Git/非package依赖、硬件free边界明确 |
| C06 待决事项/发布缺口 | R14–R17/R22及下面decision table | license/authors/version/remote处理有owner与阻断阶段，不悄悄默认授权 |
| C07 benchmark draft | PROTOCOL_DRAFT | 固定负载、计时边界、环境、1+5 schedule、正确性先行、全部失败保留、重算/公开范围明确；无性能数字 |
| C08 scope/verification/handoff | docs/whitespace results、diff、动态交接 | 无生产/数值/公开schema/硬件/旧证据变更；留commands/exits/source lock/下一动作 |

CP0 的 PASS 指上述规格和 read-only probe 证据成立。CP1–CP5 必须按依赖顺序
取得新的执行证据，禁止用 CP0 的 packet decode 或 M5 历史结果代替 M6 Demo运行。

## 后续最小验收集

| 阶段 | 必需检查 | 失败/限制处理 |
|---|---|---|
| CP1 sample | 选定25文件逐hash；原map完整保留；missing/member tamper/map tamper负控；原输入前后hash；来源/许可清单 | internal-only许可标签；任何hash失败不进入CP2 |
| CP2 Demo | 四轨迹完整阶段/原gates；原独立case auditor；既有generator/packet writer不得执行；八指标摘要；two-process determinism；protected/existing/invalid-output拒绝 | M5 OPEN/formal=false不改；failed roots原样保留；语义缺陷先单独修复复验 |
| CP3 benchmark | formal protocol/source锁在执行前；warmup+5 timed；每次parent wall/exit/log/input/product checks/audit；所有attempts和失败；recompute | 无可靠compute边界只发布end-to-end；失败batch不发布成功性能结论 |
| CP4 release content | R03–R09/R13–R17 consistency/decision/notices/CFF；build/archive内容/独立安装 | license/authors未决保持BLOCKED；不得悄悄标V1.0已发布 |
| CP5 clean clone | fresh clone/ref/venv/no hardware/no external root，README原命令；pair/hash/全checks/skip-list/required-files/report | 未测Linux明确NOT RUN；外部M1全回归分列；完整证据满足才M6 DONE |

涉及Python修改时沿用仓库命令：

```powershell
uv sync --all-extras --frozen
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen python scripts/check_docs_consistency.py
git diff --check
uv build
```

单独 docs/CP0 inventory 不产生新的数值/full-test/build通过声明。
硬件无修改，不新增compile/物理采集；旧 M5 formal roots 不重跑。

## 具体待决项与处理责任

| 决策 | 责任/最迟阶段 | 当前边界 |
|---|---|---|
| 项目许可证 | maintainer / CP4 | LICENSE尚缺；准备清单不授予任何默认license |
| sample数据许可及公开分发 | maintainer / CP4；CP1提前标状态 | 复制包装保持原字节，未确认则INTERNAL ONLY |
| citation作者/身份/identifier | maintainer / CP4 | 不从本机用户名推断作者/机构/ORCID/DOI |
| 最终版本/候选ref | maintainer / CP4–CP5 | 当前pyproject0.1.0；不自动tag或改名 |
| Linux实际验收环境 | implementation agent / CP2–CP5 | CI配置不是已执行证据；未测限制支持声明 |
| 正式benchmark机器/source/协议锁 | implementation agent / CP3 | 协议先冻结再运行，无预填耗时 |
| 远端同步/大证据分发 | maintainer / overall closeout | 已明确推迟；不授权历史改写、LFS迁移或删除证据 |

CP1 下一动作：先按 [契约 §1](M6_DEMO_CONTRACT.md) 包装25个原字节输入，
建立sample README/来源成员清单和独立hash绑定，实施必要负控，再形成CP1交付。
本段到CP0结束，不提前实现CLI或采集benchmark。
