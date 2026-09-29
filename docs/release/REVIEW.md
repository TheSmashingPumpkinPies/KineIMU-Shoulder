# M6 发布决定与本地候选验收入口

当前公开整理状态（2026-09-29）：维护者已创建
[KineIMU-Shoulder](https://github.com/TheSmashingPumpkinPies/KineIMU-Shoulder)。
独立公开候选的最新验收见 [PUBLIC_VERIFICATION](../PUBLIC_VERIFICATION.md)，
来源及新增数据许可边界见 [PUBLIC_EXPORT](../PUBLIC_EXPORT.md)。新增数据的经审查公开副本已获授权；脱敏与当前验收状态见上述报告。以下 2026-09-28 记录描述原始 M6 验收及当时的发布状态。

2026-09-28。维护者已接受英文 README、中文技术报告、项目简介、MIT、CC0、
Hongbo Liao 版权署名和首发版本 0.1.0；经聊天解释后回复“三项同意”，确认
版权年份 2026、引用作者 Hongbo Liao、公开仓库 owner TheSmashingPumpkinPies。
全部明确决定记于 [ADR-012](../adr/ADR-012-release-documentation-and-license-selection.md)。

## 已接受决定

| 项目 | 决定 | 落地与边界 |
|---|---|---|
| 文档 | 英文 [README](../../README.md) + 中文 [技术报告](../M6_TECHNICAL_REPORT.md)；接受研究框架简介 | 保留采集/合成验证证据范围、人体/临床限制 |
| 原创代码及文档 | MIT；Copyright (c) 2026 Hongbo Liao | 根 [LICENSE](../../LICENSE) 为完整正文；第三方及历史来源材料保留原许可 |
| 原创合成 sample | 确认有权公开，CC0-1.0 | [许可附页](../../datasets/samples/m6_synthetic/LICENSE.md) 仅覆盖25个选定原创成员；原数据/map/provenance/历史声明不改 |
| 引用作者 | Hongbo Liao；given-names Hongbo、family-names Liao | [CITATION.cff](../../CITATION.cff) 与 package author 一致；机构/ORCID 不填，日期/DOI 尚无则省略 |
| 公开仓库 | TheSmashingPumpkinPies/kineimu-shoulder | URL 为已接受的发布目标；当前 origin 仍为管理仓库，不声称已经创建或公开 |
| 首发版本 | 0.1.0 | 候选提交由构建/验证记录锁定；实际发布日期和 tag 按后续发布处理 |

许可来源为 [MIT 官方文本](https://opensource.org/license/mit)、
[CC0 说明](https://creativecommons.org/publicdomain/zero/1.0/)及
[CC0 法律文本](https://creativecommons.org/publicdomain/zero/1.0/legalcode)。
第三方版本、义务及算法引用见 [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md)。
CFF 按 [官方1.2.0规范](https://github.com/citation-file-format/citation-file-format/blob/1.2.0/schema-guide.md)
进行完整 YAML/schema 验证；作者另经明确批准，不从版权持有人或本机账号推断。

## 验证与后续动作

新候选的许可/CFF/文档一致性、构建/归档和独立 wheel/sdist 安装结果见
[CP4 候选验证](../../experiments/M6_CP4_FINAL_20260928/README.md)。
CP4全部门已通过；[CP5 fresh-clone报告](../../experiments/M6_CP5_20260928/REPORT.md)
及[完整要求覆盖](../../experiments/M6_CP5_20260928/COVERAGE.md)记录本地M6 DONE。
新clone/cache/venv、两次Demo/独立审核、full877+2预期skip、静态/文档/构建/独立安装PASS。
CP4外部M1 full879/0skip保持分列；Linux NOT RUN，实际公开发布未执行。
[旧内部预览](../../experiments/M6_CP4_20260928/README.md) 保持原样，不冒充新制品。

当前根 LICENSE、CITATION 和 pyproject 已填写所有已确认的元数据。
候选构建不等于公开发布。公开仓库创建、push/tag/Release/PyPI、历史改写和
大证据迁移仍留待后续对应授权；不改动当前 origin，也不自动建立远端仓库。
