# 山海纳珍录 - 工程项目采购管理系统

工程类采购全流程数字化管理系统。

## 项目结构

```
ShanHaiNaZhen_system/
├── backend/          # FastAPI 后端（可选 web/dist 存放打包后的静态前端）
├── frontend/         # Vue 3 前端
├── scripts/          # 部署脚本（build_release.bat / start.bat）
├── VERSION.txt       # 发版版本号（首行，供后端读取）
└── PRDs/             # 产品需求文档
```

## 快速开始

### 1. 初始化数据库

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cd ..
python scripts/init_db.py
```

默认管理员：admin / admin123

**已有数据库升级**：若从旧版本升级且数据库结构有变更，在项目根目录执行（无需激活 venv）。**日常修改代码无需运行**，仅在进行数据库迁移时执行：

```bash
cd d:\ShanHaiNaZhen_system
backend\venv\Scripts\python.exe scripts\migrate_add_columns.py
```

### 2. 启动后端

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

若已构建前端（存在 `frontend/dist` 或 `backend/web/dist` 且含 `index.html`），**同一端口** 会同时提供 **网页 + API**；开发时常用 **8000**，封装一键启动默认 **18080**（见下）。

#### 封装 / 生产（办公室单机）

1. **一键构建网页并同步到后端**：`scripts\build_release.bat`（`npm run build:pack` + 镜像到 `backend\web\dist`）
2. **启动**：`scripts\start.bat`（监听 `0.0.0.0`，默认端口 **18080**，网页与 API 同端口；**8000 常被占用**，故单机封装改用该默认）  
   - 改用其他端口：启动前执行 `set SHANHAI_PORT=8000`（或与 `stop.bat` 使用同一变量，便于结束进程）  
   - 兼容旧习惯：仍可双击 `scripts\start_production.bat`（内部转调 `start.bat`）

完整步骤、升级与备份见 **[docs/deploy-packaged.md](docs/deploy-packaged.md)**。给非开发人员看的简明步骤见 **[docs/小白操作说明.md](docs/小白操作说明.md)**。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

本地开发访问 http://localhost:5173；系统访问地址：http://shanhainazhen.com

#### 在 Cursor / VS Code 里启动（推荐）

- **`Ctrl+Shift+P`** → 输入 **`Tasks: Run Task`**（或菜单 **终端 → 运行任务…**），选择：
  - **`[Backend] FastAPI :8000`** — 后端（与 Vite 代理一致；封装单机请用 `start.bat` 默认 **18080**）
  - **`[Frontend] Vite :5173`** — 前端
  - **`[Full] 同时启动前后端`** — 一次开两个终端
- 通过任务打开的终端，标签会显示 **任务名**（不再全是 `cmd`）。本仓库 `.vscode/settings.json` 已配置终端标题模板。
- **终端里的网址**：在 Windows 上请用 **`Ctrl + 单击`**（macOS 为 **`Cmd + 单击`**）打开 `http://localhost:5173/` 等链接。若仍无法点击，将默认终端改为 **PowerShell**：在 `settings.json` 中取消注释 `"terminal.integrated.defaultProfile.windows": "PowerShell"`，或使用 **Windows Terminal** 作为外部终端。

**注意**：实时同步（多窗口自动刷新）依赖后端 WebSocket。请先启动后端，否则控制台可能出现 `ws proxy socket error: ECONNRESET`，可忽略。

### 4. 文件存储（集中式）

- **元数据**：SQLite 数据库，默认在 **`backend/database/shanhai.db`**（可用环境变量 `SHANHAI_DATABASE_PATH` 覆盖）。
- **流程 Word、目录、归档与上传文件**：均在 **`backend/data`**（`procurement_process`、`archived_file` 等，可用环境变量 `PROCUREMENT_PROCESS_ROOT` / `ARCHIVED_FILE_ROOT` 覆盖）。
- 办公室部署：**一台电脑运行 `scripts\start.bat`（默认 18080）**，其他人只用浏览器访问即可。

### 5. 数据备份

```bash
python scripts/backup.py
```

## 权限说明（导出）

- **导出 Excel**（工程项目清单、智能台账）：单机模式下由后端统一鉴权，浏览器访问封装端口（默认 **18080**）即可调用。
- 采购清单页的「导出 EXCEL」为前端生成 CSV，不另走后端权限。

## 功能模块

- **工程项目管理**：立项、清单、文件夹自动创建
- **采购流程**：四步式表单、Word生成、五选二、补充协议
- **归档管理**：文件上传、合同标识、台账关联
- **智能台账**：自动生成、导出Excel、主合同补充协议关联
- **系统配置**：Word 模板路径等

## 技术栈

- 前端：Vue 3 + Element Plus + Pinia + TypeScript + Vite
- 后端：Python FastAPI + SQLAlchemy + SQLite
- 文件存储：集中在运行后端的 **`backend/data`**（局域网浏览器访问封装端口，默认 **18080**）

## 测试与试运行

- **接口自动化**：`cd backend`，安装 `pip install -r requirements-dev.txt`，执行 `pytest tests -q`（使用临时库，不污染 `database/shanhai.db`）。说明见 [docs/TESTING.md](docs/TESTING.md)。
- **后端 HTTP 冒烟**（需先启动 uvicorn）：`python scripts/smoke_http.py`
- **种子数据**：`python scripts/init_db.py` 后执行 `backend\venv\Scripts\python.exe scripts\seed_test_data.py`（轻量）；按 `docs/seed_data_template.md` 大批量灌数见 `scripts/seed_from_template.py --clear`（归档占位 PDF + **台账** + 默认随机 50 条流程 docx；**仅删三个模板工程不灌数**用 `--clear-only`；`--no-process-files` / `--seed` 见 `--help`）。**详细教程**：[docs/seed_from_template_guide.md](docs/seed_from_template_guide.md)
- **定制造数信息表**：[docs/seed_data_template.md](docs/seed_data_template.md) 填好发回即可扩展种子脚本
- **仅人工 UAT 清单**（分阶段）：[docs/UAT-manual-phases.md](docs/UAT-manual-phases.md)
