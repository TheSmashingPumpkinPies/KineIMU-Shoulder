# M6.0 / CP0 — contract freeze evidence

日期：2026-09-28；入口 `main` / `566ce905e7fea5ddbc2f33b3432c68fd0c2b6907`。
交付：[Demo契约](../../docs/M6_DEMO_CONTRACT.md)、
[要求/验收映射](../../docs/M6_RELEASE_CHECKLIST.md)、
[benchmark预登记草案](../../benchmarks/demo/PROTOCOL_DRAFT.md)。
本根是新的规格审查/只读盘点证据；没有执行AHRS、完整Demo或性能测量。
CP0 PASS为规格放行；CP1–CP5仍OPEN。实际检查见checks.json。

`inventory.json` 记录25文件/4,539,058 bytes及Git字节匹配，8个Q流的完整
decode/QC/count/time身份、before/after hashes、真实API签名、40项exporter来源依赖，
13项不创建路径的现有防护探针。输入原map的36成员与sample选定24成员边界明确。
同一只读工具在独立新scratch根复核，inventory字节一致；原输入不变。
`inventory-tool.txt` 是此次只读探针源码快照，可由Python直接运行；不修改生产算法。
`inventory-probe.log` 留存实际成功probe输出；完整命令/退出见 `checks.json`。

启动时sandbox显示历史CP3/CP4 evidence apparent deletions；normal-permission
`git status --porcelain --untracked-files=no` exit0/empty证明入口tracked tree clean。
未修复/删除/重建任何旧数据。agent_context完整输出保存在本地scratch
`.tmp-m60-startup-context.txt`，不作为冻结输入或发布依赖。
初次probe因PATH无法启动uv --version退出1，尚未创建CP0根；改用实际存在的
uv0.12.5绝对路径后完成盘点。此失败是工具launch，不是算法/输入gate失败；
保留在checks中。Demo目标命令仍要求用户环境可从PATH调用uv，不依赖此本机路径。

## 复核方式

从相同入口source锁的仓库根、含analysis依赖的环境，在不存在的新root运行：

```powershell
.venv/Scripts/python.exe experiments/M6_CP0_20260928/inventory-tool.txt .tmp-m60-independent-probe
```

脚本拒绝已存在/原证据根；不要传本根，也不要重用scratch。
探针工具的uv身份调用使用本机USERPROFILE/.local/bin/uv.exe；这是盘点环境实测
路径，不是Demo依赖。其他环境复核应记录工具适配/实际uv身份，不能声称同一工具字节锁。
新HEAD的source_head/source hashes会变，不能据此断言输入失配；可独立比较inputs、
captures、input audits及guard结果，源码身份差异单列。

文档/whitespace检查：

```powershell
.venv/Scripts/python.exe scripts/check_docs_consistency.py
git diff --check
```

本段最终检查/人工requirement review见checks.json；交付快照SHA256SUMS.json
只覆盖本段具名文件，不覆盖旧证据或自身。提交后可用
`git log -1 --format=%H -- docs/M6_DEMO_CONTRACT.md`解析CP0交付锁，
并用`git rev-parse HEAD`核对当前state tip。
下一步M6.1/CP1 sample包装；CP2–CP5及M6总验收仍OPEN。
