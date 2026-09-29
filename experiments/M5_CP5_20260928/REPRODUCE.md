# M5 复现命令与来源锁

以下 PowerShell 命令从仓库根执行。Python 3.12.14、uv 0.12.5 与 `uv.lock`
冻结；numpy 2.5.2、scipy 1.18.1、pandas 3.0.5、imufusion 1.3.3、imucal 2.6.0。
`uv sync --all-extras --frozen` 安装依赖。原验收运行的命令/exit/hash 见各
checkpoint 报告，CP5 检查见 `checks.json`；本节的新输出路径不是旧命令的重写。

## 1. 当前 checkout 的项目检查

首次使用下列 temp 名；已存在时换新后缀，保留旧根。

```powershell
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    $env:PATH = "$env:USERPROFILE/.local/bin;$env:PATH"
}
uv sync --all-extras --frozen
$env:KINEIMU_M1_RAW_ROOT = '<external-data>/kineimu_m1_usb_30min_20260925_01'
.venv/Scripts/python.exe -m pytest --basetemp .tmp-m55-reproduce-full --tb=short
.venv/Scripts/python.exe -m pytest experiments/M5_CP4_STAGE_E4_20260928/test_worker_identity.py --basetemp .tmp-m55-reproduce-guards --tb=short
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy --strict kineimu_shoulder
.venv/Scripts/python.exe scripts/check_docs_consistency.py
git diff --check
uv build --out-dir .tmp-m55-reproduce-build
```

外部根缺失时外部测试可能 skip；这不复现完整 CP5/CP4 检查。CP5 实际运行
两项外部测试的结果须为 passed，完整 suite 的 skip 为零。固件构建不适用本次
文档/索引收口。clean-clone 无外部数据演示的验收属于 M6。

## 2. 只读核对本次完整证据索引

以下命令核对每个列出的文件及两次 canonical 库存，外部根只读。
不导入生产算法、不写旧证据；任一缺失/改字节/漏项即异常退出。
它核对来源与保留字节，不重新计算数值误差或代替原独立 numerical audit。

```powershell
@'
import hashlib, json, os
from pathlib import Path
from zipfile import ZipFile
root = Path.cwd()
index = json.loads((root / 'experiments/M5_CP5_20260928/evidence-index.json').read_bytes())
def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
for name, expected in index['repo_file_sha256'].items():
    assert digest(root / name) == expected, name
for group in index['canonical_inventory_groups']:
    base = root / group['root']
    actual = {p.relative_to(root).as_posix() for p in base.rglob('*') if p.is_file()}
    expected = {n for n in index['repo_file_sha256'] if n.startswith(group['root'] + '/')}
    assert actual == expected and len(actual) == group['files'], group['root']
external = Path(os.environ.get('KINEIMU_M1_RAW_ROOT', index['external_root_at_verification']))
for name, expected in index['external_file_sha256'].items():
    assert digest(external / name) == expected, name
for name, archive in index['source_archives'].items():
    with ZipFile(root / name) as z:
        expected = archive['member_sha256']
        assert len(z.namelist()) == len(expected) and set(z.namelist()) == set(expected), name
        assert all(hashlib.sha256(z.read(n)).hexdigest() == h for n, h in expected.items()), name
print('PASS: all retained evidence bytes, complete inventories, external originals and source archives')
'@ | .venv/Scripts/python.exe -
```

CP5 本段还核对原 63 项 runtime source binding 未变及所有原验收 disposition。
误 hash 的负控制见 `hash-control.json`；它只在内存中改变期望 hash，原文件
不变。索引自己的 hash 在 `evidence-audit.json`，最终交付文件及日志 hash
在 `delivery-sha256.json`，均不自包含自己的 hash。

精确提交可从 Git 解析，不使用动态状态文件推测数值锁：

```powershell
git log -1 --format=%H -- experiments/M5_CP5_20260928/evidence-index.json
git log -1 --format=%H -- HANDOFF.md
git rev-parse HEAD
git status --short --untracked-files=no
```

## 3. 重新执行数值工具

在**独立 checkout** 使用对应旧源码锁；不要在当前交付 checkout 换分支，
不要运行旧的固定路径 launcher（会碰已消费的 formal/operational 根）。
每个 checkpoint 的运行 manifest 都记录 exact code/source/config/runtime hash。
CP1/CP2 source map、CP3/CP4 的 ZIP 成员 hash 和环境必须先核对；仅有同一
commit 不足以证明实际运行源码字节相同。新进程 PID/路径/日志不同是正常的；
不同 Git/source provenance 时不声称整个 canonical manifest 字节相同。

| checkpoint | checkout 锁 | 原 source/runtime 身份证据 |
|---|---|---|
| CP1 | `ee0741334e430c7cf8b5b9845d0a9b48426fecad` | run1/manifest.json `source_hashes` |
| CP2 | `92d06d0589689417162eb80d351566045c7c25b7` | retry1/run1/manifest.json `source_file_sha256` |
| CP3 | `01c4e23bd82bcbec6ae775bf6db6c67471fa6ac3` | source-lock-01c4e23.zip，86 原运行成员；source-byte-retention.json |
| CP4 数值 | `a72bdd18dd3567bb3b043c4cd6c75b16b7311cf9` | source-lock-a72bdd18.zip，63 原运行成员；原 EOL 绑定 |
| CP4 审计 | `fbcb118ba5eaf54c739767ac36ac9bdb129ad3e5` | audit-tool-lock-fbcb118b.zip；E4 source/worker identity 说明 |

CP3/CP4 仅在独立对应 checkout 恢复 ZIP 内的**原运行源码**并核对每项
manifest hash（不解压覆盖 raw、formal 根或当前 checkout）。CP1/CP2 如 Git
checkout 的行尾与原 map 不符，逐项确认内容只差 LF/CRLF，并以原 map 的
精确 hash 核对恢复结果；内容差异不能靠行尾处理获准。
CP4 仍严格使用其已声明的两个 path/hash 对，不增加宽泛的 EOL 豁免。

在各自 checkout，设置绝对 `PYTHONPATH` 和线程上限后执行：

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
```

CP1（源工具，不是 AHRS/下游验收）：

```powershell
.venv/Scripts/python.exe examples/m5_sensor_source.py --output .tmp-m55-reproduce-cp1/run1
.venv/Scripts/python.exe examples/m5_sensor_source.py --output .tmp-m55-reproduce-cp1/run2
```

CP2（30 CLEAN 与两项 comparison）：

```powershell
.venv/Scripts/python.exe examples/m5_baseline.py --output .tmp-m55-reproduce-cp2/run1
.venv/Scripts/python.exe examples/m5_baseline.py --output .tmp-m55-reproduce-cp2/run2
.venv/Scripts/python.exe experiments/M5_CP2_20260926/audit.py --root .tmp-m55-reproduce-cp2 --output .tmp-m55-reproduce-cp2-audit.json
```

CP3（完整 1,142；不要只运行以前 46 个失败）：

```powershell
.venv/Scripts/python.exe examples/m5_perturbation.py --output .tmp-m55-reproduce-cp3/run1 --workers 3
.venv/Scripts/python.exe examples/m5_perturbation.py --output .tmp-m55-reproduce-cp3/run2 --workers 3
.venv/Scripts/python.exe experiments/M5_CP3_20260926/audit.py --root .tmp-m55-reproduce-cp3 --output .tmp-m55-reproduce-cp3-audit.json
```

旧 CP2 partial/CP3 failure 清单所引用的保留文件也必须可访问；auditor 会核对
其不可变性。原 full matrix 需要的操作 scratch 与 canonical 目录分开。

CP4（实际读完整合成 Q、Node B、外部 11 项，不产生 acquisition）：

```powershell
$env:KINEIMU_M1_RAW_ROOT = '<external-data>/kineimu_m1_usb_30min_20260925_01'
.venv/Scripts/python.exe -m kineimu_shoulder.validation.formal_replay --output .tmp-m55-reproduce-cp4/run1 --operation .tmp-m55-reproduce-cp4-operation1.json --root $env:KINEIMU_M1_RAW_ROOT
.venv/Scripts/python.exe -m kineimu_shoulder.validation.formal_replay --output .tmp-m55-reproduce-cp4/run2 --operation .tmp-m55-reproduce-cp4-operation2.json --root $env:KINEIMU_M1_RAW_ROOT
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_B_20260927/audit.py .tmp-m55-reproduce-cp4/run1/B .tmp-m55-reproduce-cp4-run1-B-audit.json
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_C_20260927/audit.py --run .tmp-m55-reproduce-cp4/run1/C --output .tmp-m55-reproduce-cp4-run1-C-audit.json
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_D2_20260927/audit.py --run .tmp-m55-reproduce-cp4/run1/D --root $env:KINEIMU_M1_RAW_ROOT --output .tmp-m55-reproduce-cp4-run1-D-audit.json
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_B_20260927/audit.py .tmp-m55-reproduce-cp4/run2/B .tmp-m55-reproduce-cp4-run2-B-audit.json
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_C_20260927/audit.py --run .tmp-m55-reproduce-cp4/run2/C --output .tmp-m55-reproduce-cp4-run2-C-audit.json
.venv/Scripts/python.exe experiments/M5_CP4_STAGE_D2_20260927/audit.py --run .tmp-m55-reproduce-cp4/run2/D --root $env:KINEIMU_M1_RAW_ROOT --output .tmp-m55-reproduce-cp4-run2-D-audit.json
```

再比较两根所有 35 canonical 产品及外层 checksum 的字节和 inventory。
这些是新的数值复现与六项审计，**不自动成为新的 CP4 正式 pair 放行**。
E4 原 pair auditor 绑定原 source lock、operation、launcher/worker、Windows
probe 和固定 E4 日志路径，不能仅改 `--output` 就安全重跑。
核对已接受 pair 使用第 2 节只读 hash 命令；若将来要新正式验收，应在新的
工具锁中显式参数化全部 operation/audit 输出路径，测试后留证，不改旧 E4。

全部数值工具要求 fresh output；exit 非 0 保留部分输出和错误日志，禁止续写、
修补或重用失败根。新复现命令在本次 CP5 仅经 CLI/来源审查，未再次启动昂贵
CP2/CP3/CP4 numerical collection；实际原命令与成功证据继续由原报告支撑。
