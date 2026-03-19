# 山海纳珍录 - 工程项目采购管理系统

工程类采购全流程数字化管理系统。

## 项目结构

```
ShanHaiNaZhen_system/
├── backend/          # FastAPI 后端
├── frontend/         # Vue 3 前端
├── client_agent/     # 用户电脑文件服务（分布式存储）
├── scripts/          # 部署脚本
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

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

本地开发访问 http://localhost:5173；系统访问地址：http://shanhainazhen.com

**注意**：实时同步（多窗口自动刷新）依赖后端 WebSocket。请先启动后端，否则控制台可能出现 `ws proxy socket error: ECONNRESET`，可忽略。

### 4. 客户端代理（可选，分布式部署时使用）

```bash
cd client_agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 5. 数据备份

```bash
python scripts/backup.py
```

## 功能模块

- **工程项目管理**：立项、清单、文件夹自动创建
- **采购流程**：四步式表单、Word生成、五选二、补充协议
- **归档管理**：文件上传、合同标识、台账关联
- **智能台账**：自动生成、导出Excel、主合同补充协议关联
- **系统设置**：用户管理、Word模板（管理员）

## 技术栈

- 前端：Vue 3 + Element Plus + Pinia + TypeScript + Vite
- 后端：Python FastAPI + SQLAlchemy + SQLite
- 文件存储：本地/分布式（各用户电脑）
