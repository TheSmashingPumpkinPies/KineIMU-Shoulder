# M6 Development Plan — Hardware-free Demo and Release

日期：2026-09-28（Asia/Shanghai）。当前状态：**CP0–CP5 PASS；M6 本地 V1 验收 DONE。**

当前阶段交付与决定：[发布审定页](docs/release/REVIEW.md)、
[技术报告](docs/M6_TECHNICAL_REPORT.md)、[CP4 候选制品验证](experiments/M6_CP4_FINAL_20260928/README.md)。
维护者已明确同意英文 README、中文报告、项目 MIT、原创 sample CC0、版权/作者
Hongbo Liao、年份 2026、公开仓库目标 TheSmashingPumpkinPies/kineimu-shoulder 及版本0.1.0。
CFF/文档/许可、full879无skip、静态检查、构建/归档和独立安装均通过；最终提交字节另留证。
CP5 clean clone/fresh environment 已独立通过：[总报告](experiments/M6_CP5_20260928/REPORT.md)、
[R01–R22覆盖](experiments/M6_CP5_20260928/COVERAGE.md)。新clone/cache/venv、两次完整demo/独立审核、
full877+2预期外部数据skip、静态/文档/build/archive/独立安装均有实际记录。
实际公开发布未执行，需对应明确授权；Linux NOT RUN。
CP1/CP2/CP3 当前通过证据分别见
[sample](experiments/M6_CP1_20260928/README.md)、
[demo](experiments/M6_CP2_20260928/README.md)、[benchmark](benchmarks/demo/REPORT.md)。

以下保留原 CP0 规划基线和冻结验收定义；其中“尚未”“当前只完成”及 CP0 下一动作
均描述当时状态，不作为当前进度。最终阶段依赖和通过判据保持有效。
规划入口：`main` / `b4dd2962abb786bd51f765f973dd341b3adf8923`。
M0–M5 在各自记录范围 DONE；硬件冻结。

本计划落实 [M6 验收要求](ACCEPTANCE_CRITERIA.md)、
[路线图](02_DEVELOPMENT_ROADMAP.md) 和
[M5 交接输入](experiments/M5_CP5_20260928/M6_HANDOFF.md)。
规范、公开 schema、算法语义及已接受 ADR 保持其原有权威；本计划不重新定义它们。
下文 CP 编号均为 **M6 内部 checkpoint**，不得与 M5 同名证据混用。

## 最终交付目标

新用户从 clean clone 安装冻结依赖，不连接 XIAO、不设置外部 M1 raw root，
即可执行一个完整双节点 synthetic recording 回放演示，获得 processed、derived、
QC/provenance 和可阅读摘要。仓库同时提供可追溯示例数据、准确的技术文档、
可复现 benchmark、技术报告、许可证、引用及第三方声明，满足发布候选验收。

M6 DONE 表示软件及本地发布候选满足 M6 验收；远端 push、tag、GitHub Release、
PyPI 上传或仓库改名的实际执行另记发布状态，需对应明确授权。
初版规划段未实施新入口、数据包装、benchmark 或发布。维护者随后明确进入M6.0；
当前只完成契约/要求映射/benchmark草案和只读盘点，仍未实施Demo或执行性能测量。

## 已盘点基线与默认方案

| 项目 | 当前可复用资产 / 缺口 | M6 决策方向 |
|---|---|---|
| 完整传感器链路 | `examples/m5_baseline.py` 是 30 个 CP2 用例的正式验收入口，并非简短用户 demo；`kineimu_shoulder/validation/stored_demo.py` 可执行既有 processing/1.1 的四条完整 Q 回放 | 新增薄演示入口，优先调用既有 stored-Q exporter；不重写校准、AHRS、同步、M3/M4 或独立 oracle |
| 示例输入 | `experiments/M5_CP1_20260926/run1` 留存 F90、AL90、AR90、T-MIX、metadata、annotations、SI 参考及固定 digest map；原 CP1 报告列出完整生成产物约 10 MB | 默认复用四轨迹完整输入集合；CP0 实测最小依赖集合的文件数/大小/hash，不把原生成目录大小当新发布包大小 |
| 输入绑定 | `stored_demo.input_audit()` 绑定原 digest map，并审核四轨迹输入及公共文件 | 先以原目录为只读来源；若包装到新 sample 目录，保持原字节与原 map，不删减成单轨迹后绕过输入审核 |
| 输出报告 | 原 runner 使用 `m5-report/1.0`、CP4/B 和历史 OPEN 状态；CP2报告也保留历史说明 | 保留原 runner 结果；另写明确标为 M6 demo 的用户摘要和运行清单，区分“本次演示成功”与“原 checkpoint 状态” |
| 自动化 | `.github/workflows/python-ci.yml` 已包含 frozen sync、pytest、Ruff、mypy、docs、build，运行于 Ubuntu；现有数值确定性证据在 Windows | 加入无硬件 demo smoke 检查；分别记录实际 Windows/Linux 结果，不能把现有 CI 配置当新 demo 跨平台证据 |
| 打包 | pyproject 为 0.1.0；sdist 仅包含 package，wheel 包含 package；部分 validation 代码从仓库根读取 protocols/fixtures | 必须区分 clean-clone demo 与 wheel API 安装；不声称 wheel 单独可运行 repo demo；CP4 核对 sdist 的 README、许可与必要构建元数据 |
| 发布治理 | 根目录未找到 `LICENSE`、`CITATION.cff`、`THIRD_PARTY_NOTICES.md`；[第三方兼容说明](THIRD_PARTY_COMPATIBILITY.md) 明确要求发布前选定项目许可 | 项目及 sample 许可、作者/引用元数据由维护者确认，作为 CP4 发布门；准备材料可先推进，不擅自授予许可证 |
| 性能 | `benchmarks/` 目前仅占位文件；M5 pytest/validation 运行时间不是分析性能证据 | 新建 release benchmark 的预登记协议、runner、原始结果及报告；不预填性能数字 |
| 技术报告 | M2–M5 文档和 CP5 coverage/index 可引用；无 M6 发布总报告 | 整理用户入口、证据范围、复现方法和限制；历史实验文档不改写 |

优先选择已有可审核的四轨迹回放，而非只运行精确姿态输入：
它覆盖屈曲、左右外展及移动胸廓，且从 `.kimu` 观测进入校准/AHRS 全链路。
静态 Markdown 摘要是默认最小展示形式；可用现有工具增加图，但图形不引入新运行时依赖。
不增加账户、云平台、大 dashboard、新平滑度算法或临床解释。

## 阶段、交付物与 checkpoint

依赖顺序：**M6.0/CP0 → M6.1/CP1 → M6.2/CP2 → M6.3/CP3 → M6.4/CP4 → M6.5/CP5**。
下面文件名为各阶段交付位置；CP0已交付，后续文件仍是目标，不代表已通过。

| 阶段 | 交付目标与计划产物 | Checkpoint 通过条件 |
|---|---|---|
| **M6.0 — 契约与发布缺口冻结** | `docs/M6_DEMO_CONTRACT.md`：输入文件依赖/大小/hash、默认四轨迹、完整处理阶段、命令/输出/退出约定、证据显示规则、支持环境；`docs/M6_RELEASE_CHECKLIST.md`：M6 每条要求→阶段→证据；benchmark 预登记草案；许可/作者待决项 | **CP0 规格放行。** 每条 M6 要求有归属和可观察判据；确认实际可调用接口、fresh output 防护、最小 input 集合；明确 clean clone 不依赖本机绝对路径/外部 raw；默认方案及待决事项记录齐全，未决许可明确阻断 CP4而非悄悄采用默认许可 |
| **M6.1 — 可发布示例数据与来源** | `datasets/samples/m6_synthetic/README.md` 与来源清单；选定只读原目录绑定或原字节复制包装；记录轨迹、生成锁、配置、单位/坐标、合成标签、data license 状态、大小及 sha256；独立标注保留 | **CP1 输入放行。** clean checkout 能定位所有必要文件；与原 CP1 map 的逐文件绑定正确；运行前后 raw hash 相同；缺文件、hash 失配及不支持输入有明确拒绝；无人体/个人数据；许可未决时标 INTERNAL ONLY，不宣称可公开发布 |
| **M6.2 — 一次命令完整演示** | `examples/m6_demo.py` 和 `docs/M6_DEMO.md`；调用已有 processing/1.1 stored-Q 链路，输出机器产物、运行清单、`summary.md`；必要的入口/报告集成测试；最小展示不依赖直播硬件 | **CP2 demo 放行。** 四轨迹都实际运行；从 packet/QC/SI→校准→AHRS→显式对齐/同步→M3→M4→摘要，不能用精确姿态代替；数值/QC 与原门限及独立标签一致；报告有单位、有效性、原因、证据标签/适用范围；失败 exit 非零且保留产物；已有目录拒绝覆盖；同锁两次独立进程的确定性数据一致，运行时间/路径等变化字段单独声明 |
| **M6.3 — 可复现性能基准** | `benchmarks/demo/PROTOCOL.md`、runner、原始逐次结果、机器/配置/source/input/lock hash、`REPORT.md`；区分端到端回放及生产计算计时 | **CP3 benchmark 放行。** 协议先于正式结果冻结；正确性检查通过后计时；完整保留预定重复和失败，不选最快一次；每个公开性能数字能由命令和原始数据重算；报告机器及样本规模、计时边界、离散性；无未定义的实时性能/吞吐宣称 |
| **M6.4 — 文档、许可与发布候选包装** | README 快速开始；hardware/protocol/algorithm/validation 文档导航及限制；`docs/M6_TECHNICAL_REPORT.md`；维护者选定的 LICENSE、CITATION.cff、THIRD_PARTY_NOTICES.md；版本/构建及候选制品清单 | **CP4 内容与包装放行。** 文档链接/状态/名称一致；synthetic 与 recorded 证据区分；许可和作者元数据已明确确认；第三方版本/许可/算法引用可核查；sdist/wheel 成功构建并核对文件/元数据，在独立环境安装验证；sample 分发方式和许可明确；版本仍为0.1.0的事实不得改述为已发布V1.0 |
| **M6.5 — clean-clone 独立验收与收口** | fresh clone/fresh venv 执行记录、两次 demo 及 hash 比对、全套检查、M6 要求覆盖表、制品 hash、完整失败记录、M6 总报告及动态交接；本地 release candidate | **CP5 M6 收口。** 不继承现有 .venv、不设置 KINEIMU_M1_RAW_ROOT、不连接设备，按 README 完整成功；输入原字节不变；CP0–CP4 通过，必需文件和证据完整；自动化检查无未解决失败；实际平台验证范围明确；外部 M1 测试的预期 skip 与维护者完整 replay 检查分列；tag/发布状态与本地候选状态分别记录 |

## Demo 输入、输出及验收行为

CP0 冻结一个清晰入口，默认运行完整四轨迹；额外的单轨迹开关仅在现有接口
支持且不绕过 input audit 时采用，不为缩短 demo 修改冻结输入契约。
`examples/m5_baseline.py` 仍是历史 CP2 重现入口，不能直接改成 M6 并覆写它的含义。

每次使用新输出根，输出位置避开 `datasets/`、源码、固件、tests、已有 experiments。
演示可使用仓库内新的 `demo-output-*` 或独立工作目录；CP0 核实既有 `_protect`
规则，保留旧 formal roots 和失败产物，不能通过关闭防护来实现友好入口。

演示摘要至少包含：

- 输入身份/hash、source_type、轨迹/侧别、运行/处理版本与依赖身份。
- 八类既定核心指标的结果或不可用理由；样本/动作有效分母、排除及 QC。
- SI 机器结果；展示角度可转为 degrees，但显式标单位；速度与时间不混用。
- Observed / Derived / Assumed / Validated / Experimental 的证据意义及测试条件。
- synthetic 已知 heading/clock/alignment 是构造条件；`anatomical_eligible=false`。
- real recorded 输入若作为补充演示，缺支持证据仍为 null/invalid，不能改为 0。

现有 longitudinal summary API 保留；其 demo 示例只有复用既有合成比较而无需
新算法时才加入。它不是新增临床趋势/康复效果评分或CP2的额外数值门槛。

## Benchmark 预登记要求

CP0 草案、CP3 正式锁定以下默认协议；执行前核对适用性，任何调整先记录再运行。

1. 固定同一套四条 Q recording，不生成新随机输入；记录 A/B 样本与包数、字节量、hash。
2. 固定环境及数值线程配置，记录 OS、CPU、内存、Python、uv、依赖、源码/lock hash。
3. 定义两种独立计时：端到端回放（读入、QC、处理、标准输出写入，不含依赖安装）；
   生产处理子区间（不含 oracle/验收误差计算，仅在既有边界能可靠测量时报告）。
   不能可靠隔离时只发布端到端计时，并明确含验证开销。
4. 默认一次 warmup 加五次完整计时；每次新根和新进程，fresh AHRS；保留所有原始耗时、
   退出码及正确性结果。报告 median 和 min/max，五次重复不作总体统计推断。
5. 可报告 wall seconds 和明确定义的 node-samples/s；四轨迹串行总样本不解释为直播同步吞吐。
   是否含 startup、文件/hash/报告开销明确列出；不把 pytest 用时当 benchmark。
6. 不预设未经依据的速度目标或虚构实测性能；CP3 判据是正确、可复现和可追溯。
   原始 benchmark 日志不可丢弃失败或在同根反复覆写。

## Clean-clone 命令与环境验证

CP0 将下列**目标命令**落实为文档；`m6_demo.py` 及其参数尚未实现或测试。
clone 使用届时确认的现有 remote URL 和候选 ref，不假设仓库已改名。
安装依赖需要网络/可用缓存；hardware-free 不等于依赖安装完全离线。

```powershell
# 在独立 fresh clone、确认候选 ref 后，从仓库根执行
uv sync --extra analysis --frozen
uv run --frozen python examples/m6_demo.py --output demo-output-01
# 两次独立进程使用不同的新根
uv run --frozen python examples/m6_demo.py --output demo-output-02
```

CP5 使用 README 的实际命令，不手动修改 PYTHONPATH、补拷本机文件或借用原 .venv
来让 clean clone 成功。比较同一候选锁两次结果，不能要求新 HEAD 的 provenance
与历史 M5 运行清单全字节相同；确定性文件集/变化字段在 CP0/CP2 明确冻结。

Python/CI 必需检查沿用仓库：

```powershell
uv sync --all-extras --frozen
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen mypy
uv run --frozen python scripts/check_docs_consistency.py
git diff --check
uv build
```

clean clone 无外部 M1 数据时，既有外部数据测试可能 skip；必须保留具体列表/理由，
不声称复现了 CP4/CP5 外部证据。维护者环境另用实际 `KINEIMU_M1_RAW_ROOT`
运行全部 replay 回归并记录无 skip 结果；旧 M5 formal 数值集合无需重采集或重跑。
新 demo 必须零 skip 且没有外部 raw 依赖。固件未修改，不新设固件编译/物理采集门。

首个验收平台为已建立数值证据的 Windows。Linux smoke 在既有 Ubuntu CI 或
独立可用环境实测；若未执行，记录 NOT RUN/未验证且限制支持声明，不能声称已通过。
跨平台 canonical equality 与单平台确定性是不同结论，不默认要求二者等价。

## 变更控制与阶段失败

- 每阶段保留 source/ref、完整命令、环境、exit、输入/输出 hash、报告和精确下一动作。
  每段更新 CURRENT_TASK、必要时 PROJECT_STATUS，覆盖 HANDOFF，追加 CHANGELOG_DEV，提交有效工作。
- 入口与报告包装只补有意义的集成检查：漏阶段、输入 hash、null/evidence、现有根拒绝覆盖、
  严格失败及安装环境。纯文案修改不新增镜像实现的测试。
- 若发现真实生产缺陷，先记录复现并写失败测试；修复及受影响 checkpoint 再验收另成小段。
  公共 schema、依赖、算法或处理版本变更先按规范记录对应授权/决策；不能混入包装。
- 失败 checkpoint 保持 OPEN/FAIL 或 NOT RUN/BLOCKED 并保留实际记录；失败运行根不恢复/补写。
  修复后使用新版本/新根/新提交复验，后续 checkpoint 不越过依赖门。
- 未决许可、作者/引用元数据或最终版本目标由维护者确认。它们是具体发布决策，
  无需为同样的只读盘点、文档或可逆实现反复申请许可。
- 硬件冻结；不新增人体、动捕、临床门，不推广 synthetic 数值准确性到真实解剖测量。

## CP0 历史状态与下一动作

M6.0 已完成 [Demo契约](docs/M6_DEMO_CONTRACT.md)、
[完整要求/验收映射](docs/M6_RELEASE_CHECKLIST.md)及
[benchmark草案](benchmarks/demo/PROTOCOL_DRAFT.md)，CP0规格放行。
[盘点与检查](experiments/M6_CP0_20260928/README.md)实测最小输入25文件/
4,539,058 bytes、8流17,208样本/4,304包、API及40项来源依赖、13项路径探针。
输入原map/Git字节匹配、before/after不变，现有docs/scripts防护缺口归CP2包装验收。
默认分发决定为CP1复制25个原字节文件到sample目录，原map保留并声明未分发成员。
下一工作段 **M6.1/CP1**：按冻结契约包装sample、来源/许可状态、逐hash绑定及负控。
CP1–CP5/整体M6 OPEN；无Demo实现、性能结果、发布候选、新采集或远端发布。

## 2026-09-28 维护者发布时序决定

维护者明确决定：远程同步和历史大体积验收证据的仓库/归档分发安排，
待 M6 与总项目收口时一并处理。此前“进入 M6 前先同步 M5”的要求被替代，
M6.0 不受该同步事项阻塞。原证据与提交历史继续保留；本决定不授权 LFS
迁移、历史改写或删除证据。收口发布时参考
[同步预检方案](docs/M5_REMOTE_SYNC_PLAN_20260928.md)，明确保存及复现原来源锁
的方法，再执行相应同步和验证。
