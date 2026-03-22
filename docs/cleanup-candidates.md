# 封装前大扫除 · 候选表（只读扫描结论）

> 依据仓库根目录 `123.md` 与《封装前大扫除计划》：**阶段 1～2** 产出清单与风险；**阶段 3** 仅对「机械可证、零行为变更」项执行。  
> 扫描时间：2026-03-10（本机环境）。

---

## 1. 工具链与静态检查（全仓）

| 路径/范围 | 证据 | 建议动作 | 误判/最坏影响 | 是否建议执行 |
|-----------|------|----------|----------------|--------------|
| `backend/venv` | `python -m ruff` / `pip show ruff` → 未安装 | 可选：在 **dev** 依赖中加入 `ruff` 并配置 `F401` 等；或 CI 单独安装后跑检查 | 无业务影响；仅增加维护面 | **否**（本轮不升级依赖策略；属可选增强） |
| `frontend` | 无根级 `eslint.config.*` / `.eslintrc*`；`package.json` 无 `lint` 脚本 | 可选：后续单独 PR 增加 flat ESLint + `no-unused-vars` | 配置噪声大，易与封装目标混淆 | **否** |
| `frontend` | `npm run build`（`vue-tsc && vite build`）在本机 **Node v24** 下 `vue-tsc` 抛内部错误（`Search string not found`） | 使用团队约定 Node 版本（如 LTS 20/22）重跑；或升级兼容的 `vue-tsc`/`typescript`（属依赖策略） | 无法在坏环境下证明「构建绿」 | **不动代码**；记录环境约束 |
| `frontend` | 裸跑 `npx tsc --noEmit`：`.vue` 模块解析失败（预期）；但报告 **`useRealtimeSync.ts` 中 `Ref` 未使用**（TS6133） | 删除未使用的 `type Ref` 导入 | 极低：仅类型导入 | **是** |

---

## 2. 调试残留（`frontend/src`、`backend/app`）

| 路径 | 证据 | 建议动作 | 误判风险 | 是否建议执行 |
|------|------|----------|----------|--------------|
| `frontend/src` | 全量 `rg`：`console.` / `debugger` / `TODO` / `FIXME` → **无匹配** | 无 | — | **否**（无可删项） |
| `backend/app` | 全量 `rg`：`print(`、`breakpoint(`、`pdb`、`import pdb` → **无匹配** | 无 | — | **否** |
| `frontend/vite.config.ts` | `console.error('[Vite] 代理错误:', …)`（开发服务器代理错误） | **保留**（非业务 bundle；便于本地排错） | 删则丢失本地诊断 | **否** |

---

## 3. 注释死代码 / 大块注释旧实现

| 路径 | 证据 | 建议动作 | 误判风险 | 是否建议执行 |
|------|------|----------|----------|--------------|
| `backend/app` | 抽样 `rg` 以 `# def ` / `# class ` 等形式 → **无典型「整段旧实现」命中** | 无批量删除 | 误判会删掉仍有文档价值的注释 | **否** |
| `frontend/src` | 未做「多行 `#`」式扫描（TS/Vue 以 `//`、`/* */` 为主）；未见计划要求的可机械证明块 | 无 | — | **否** |

---

## 4. 未使用符号（有编译器/linter 报告时）

| 路径 | 证据 | 建议动作 | 误判风险 | 是否建议执行 |
|------|------|----------|----------|--------------|
| `frontend/src/composables/useRealtimeSync.ts` | `tsc` TS6133：`Ref` 已导入未使用 | 从 `vue` 的 import 中移除 `type Ref` | 极低 | **是** |
| `frontend/src/utils/format.ts` | `tsc` TS2367：`number` 与 `string` 比较（多处） | **不纳入本轮**：可能牵涉运行分支，违反「零侵入」直至单独评审 | 误判会改计算/展示 | **否**（标为「保留待确认」） |

---

## 5. `scripts/`（`print` 原则上保留）

| 脚本 | 文档/仓库引用情况 | 建议动作 | 误判风险 | 是否建议执行 |
|------|-------------------|----------|----------|--------------|
| `backup.py` | `README.md`、`docs/UAT-manual-phases.md` | **保留** | — | **否** |
| `init_db.py`、`seed_test_data.py`、`seed_from_template.py`、`smoke_http.py` | `README.md`、`docs/TESTING.md`、`docs/seed_*` | **保留** | — | **否** |
| `migrate_add_columns.py` | `README.md` | **保留** | — | **否** |
| `init_templates.py` | `PRDs/development.md` 等 | **保留** | — | **否** |
| `run_test_data.py` | `docs/测试报告_数据录入.md` | **保留** | — | **否** |
| `run_system_test.py` | `docs/系统测试报告_全功能遍历.md` | **保留** | — | **否** |
| `test_wuxuaner_archive.py` | 脚本自述 | **保留**（专项测试） | — | **否** |
| `test_edit_form_data.py` | 仅文件头自述，**未见**其他 md 引用 | **保留**：可能为一次性/手工工具；无「全仓零引用」机械证明 | 删则丢失辅助脚本 | **否**（标为「保留待确认」） |

---

## 6. 构建产物与备份（与「逻辑大扫除」分离）

| 项 | 说明 |
|----|------|
| `frontend/dist`、`**/__pycache__` | **不视为业务逻辑变更**；封装发版前可单独清理或 `.gitignore` 策略处理，与删调试代码无关。 |
| `scripts/backup.py` | **大扫除或发版前**按 `README` / `docs/UAT-manual-phases.md` 执行备份；与源码条目级清理分离。 |

---

## 7. 已执行项（阶段 3 记录）

授权说明：按计划在书面候选与风险公示后实施；本仓库任务为「实施计划并完成 todos」，故仅对表中 **是否建议执行 = 是** 的条目改代码。

| 批次 | 内容 | 验证 |
|------|------|------|
| 1 | `useRealtimeSync.ts` 移除未使用 `type Ref` | `pytest` 14 passed；`npx vite build`（见执行摘要） |

### 执行摘要

- **已执行**：`frontend/src/composables/useRealtimeSync.ts` — 移除未使用的 `type Ref` 导入（TS6133，零行为变更）。
- **跳过**：`format.ts` TS2367、`vite.config.ts` 的 `console.error`、全部 `scripts/`、`backend/app` 无调试残留项。
- **工具链**：未安装 Ruff/ESLint；`npm run build`（含 `vue-tsc`）在 Node v24 下可能失败，属环境/版本问题；使用 `npx vite build` 验证打包（不含 `vue-tsc` 步骤）。
- **UAT**：阶段 0+1 抽样为人工检查，请在发版前按 `docs/UAT-manual-phases.md` 执行；大扫除未改 API/DB。

---

## 8. 明确排除（与计划一致）

- **不对** `backend/app/api/procurements.py` 等做结构性简化或合并分支。
- **不改** OpenAPI 字段、HTTP 状态码、错误 `detail` 文案、前端依赖的 JSON 形状。
