# M6.5 / CP5 — R01–R22 release requirements coverage

冻结要求来自[发布清单](../../docs/M6_RELEASE_CHECKLIST.md)和[验收要求](../../ACCEPTANCE_CRITERIA.md)。
本表不重新定义scope/schema/algorithms/ADR。最终gate判定见本目录`acceptance.json`，
原实际记录与[总报告](REPORT.md)对应；尚未公开发布。

| ID | 要求 | 验收证据/范围 |
|---|---|---|
| R01 | Fresh clone/venv | clone-01、clone-preflight、runtime-analysis-01；无旧venv/cache/externals |
| R02 | 完整硬件free demo | demo-01/02、pair-audit；四轨迹完整sensor chain及独立oracle |
| R03 | README | 原sync/run命令在fresh clone实际执行；help/新根；当前README导航 |
| R04 | Architecture | ARCHITECTURE/技术报告；clone docs consistency；源44 Git bytes |
| R05 | Hardware docs | HARDWARE_PROFILE/firmware README/M1 result/ADR-008/009；USB PASS/BLE limit/freeze明确 |
| R06 | Protocols | DATA_FORMAT/M1/M2/SYNC及M3/M4/M5 contracts；schema/units/frames不变 |
| R07 | Algorithms | BACKEND_CONTRACTS/THIRD_PARTY_NOTICES/ADR-010；mature pinned adapters和显式processed边界 |
| R08 | Validation docs | M5 CP5 COVERAGE/REPRODUCE与技术报告；旧失败保持；本次full/JUnit/独立oracle |
| R09 | Limitations | 两份summary/README/report；synthetic/anatomical=false/assumptions/null/无临床GL/scapular声明 |
| R10 | Reproducible examples | pair-audit22 canonical+summary；frozen-products-03；strict cross-ref negative regressions |
| R11 | Sample dataset | 25输入及README/provenance/CC0；clone-preflight/sample-after-demos/clone-integrity，所有原字节未变 |
| R12 | Benchmark | CP3 PROTOCOL/REPORT/REPRODUCE；retained-integrity556；没有新测量或替代最快值 |
| R13 | Technical report | docs/M6_TECHNICAL_REPORT及本REPORT；执行锁/候选制品/证据/限制分开 |
| R14 | LICENSE | ADR-012授权、full MIT/2026 Hongbo Liao/CC0 annex；CP4 delivery与archives/install hash |
| R15 | CITATION.cff | CP4 schema gate/CFF字节绑定，approved author/title/version/URL；无虚构日期/DOI |
| R16 | Third parties | 52+2原文及57archive notice files；两installed API checks；firmware分发许可边界 |
| R17 | Release candidate | pinned build、archive-review、artifact-copy-02及独立install8 commands；0.1.0，clone≠wheel demo |
| R18 | Required checks | full-01/JUnit877+2 expected skips；clone/root Ruff、mypy33、docs/whitespace、build/install |
| R19 | Platforms | Windows实测同平台PASS；Linux NOT RUN，明示限制，CI≠结果 |
| R20 | Output/provenance | 26文件/run、两checksum、八指标及分母/evidence；M6 demo_passed与历史M5 OPEN分开 |
| R21 | Failure/path safety | CP1/CP2 controls加本次full入口/guard regressions；新根/原hash保持；不覆盖partial |
| R22 | Local vs publication | 本地acceptance/proof/state独立；未创建/push/tag/Release/PyPI；迁移/历史保留 |

R19按冻结Windows-first/未测Linux明示规则验收；R22发布执行为DEFERRED。外部M1两项skip预期；CP4完整879/0skip单列。没有未处理的required-gate失败；辅助工具失败/RED和纠正全部保留于ATTEMPTS。
