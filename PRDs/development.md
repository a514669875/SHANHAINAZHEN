# 山海纳珍录——工程项目采购管理系统
## 技术实现文档（v3.0 - 集中式文件存储，服务端 8000）

> **v3 变更摘要**：流程 Word、归档与上传文件与元数据一并落在 **运行后端的机器** `backend/data` 下。  
> **已从仓库删除**：`client_agent/`、`backend/app/services/file_proxy_service.py`、`scripts/start_office_bundle.bat`。  
> 正文后文若仍出现 `client_agent`、`file_proxy_service`、端口 8001 等，均为**历史文档示意**，以当前代码与 [README](../README.md) 为准。

---

## 一、项目概述

### 1.1 系统定位
基于PRD.md和UI.md文档，为采购管理员小组（5人左右）设计的本地化办公系统，专注"工程类采购"全流程数字化管理。

### 1.2 核心目标
| 目标 | 指标 |
|------|------|
| 数据录入 | 相同字段只填写1次，不重复填写 |
| 文件管理 | 文件夹及文件命名0手动 |
| 台账生成 | 台账生成0手动 |
| 流程表单 | 生成标准化的流程表单 |
| 工作效率 | 提高70% |
| 工作出错率 | 实现0% |
| 运行配置 | i3处理器/4GB内存即可流畅运行 |
| **文件存储** | **集中在运行后端的 `backend/data`（与数据库同机）** |

### 1.3 部署约束
- **全部本地化**：前后端、数据库、文件存储均在办公室局域网内（无公有云依赖）
- **集中式存储**：流程目录、归档目录、上传文件与 SQLite 均在 **服务器（8000）本机**
- **浏览器访问**：组员通过 `http://服务器IP:8000` 使用系统；不在组员电脑上落业务文件

---

## 二、技术架构设计

### 2.1 整体架构图（分布式文件存储版）

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      用户层 (Web Browser)                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  采购管理员  │  │  采购管理员  │  │  采购管理员  │  │  系统管理员  │  │  其他用户   │          │
│  │   电脑A     │  │   电脑B     │  │   电脑C     │  │   服务器    │  │   电脑D     │          │
│  │  (用户1)    │  │  (用户2)    │  │  (用户3)    │  │  (管理员)   │  │  (用户4)    │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                │                │                 │
│         │  文件存储       │  文件存储       │  文件存储       │  数据库        │  访问访问        │
│         │  共享文件夹     │  共享文件夹     │  共享文件夹     │  元数据        │  所有资源        │
│         │                │                │                │                │                 │
│         └────────────────┴────────┬───────┴────────────────┴────────────────┘                 │
│                                   │                                                             │
│                          局域网 (HTTP/HTTPS + SMB)                                              │
└───────────────────────────────────┼─────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────────────────────────┐
│                                   应用服务层 (管理员电脑/服务器)                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                            Nginx (反向代理/静态文件服务)                                  │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                             │
│  ┌─────────────────────────────────▼─────────────────────────────────────────────────────────┐   │
│  │                          Python FastAPI (后端API服务)                                       │   │
│  │  - 用户认证与权限控制                                                                       │   │
│  │  - 业务逻辑处理                                                                             │   │
│  │  - 文件元数据管理（记录文件存储位置）                                                        │   │
│  │  - 文件访问代理（路由到对应电脑获取文件）                                                     │   │
│  │  - 台账自动生成                                                                             │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                             │
│  ┌─────────────────────────────────▼─────────────────────────────────────────────────────────┐   │
│  │                     Vue 3 + Element Plus (前端应用)                                        │   │
│  │  - 单页面应用 (SPA)                                                                         │   │
│  │  - 响应式界面                                                                               │   │
│  │  - 组件化开发                                                                               │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┼─────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────────────────────────┐
│                                   数据存储层 (分布式)                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────┐ │
│  │   用户电脑A          │  │   用户电脑B          │  │   用户电脑C          │  │  管理员电脑    │ │
│  │   文件存储           │  │   文件存储           │  │   文件存储           │  │  SQLite数据库  │ │
│  │   (经办项目文件)     │  │   (经办项目文件)     │  │   (经办项目文件)     │  │  (元数据)     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 文件存储方案

#### 2.2.1 存储架构

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    文件存储分布示意图                                            │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  管理员电脑 (服务器)                          用户电脑A (张三)                                   │
│  ┌─────────────────────┐                     ┌─────────────────────┐                           │
│  │   SQLite数据库       │                     │   文件存储           │                           │
│  │   - 工程项目表       │                     │   - 张三经办的项目   │                           │
│  │   - 采购项目表       │◄──────元数据───────►│   - 流程文件         │                           │
│  │   - 台账表           │   (记录文件位置)     │   - 归档文件         │                           │
│  │   - 文件元数据表     │                     │   - 扫描件           │                           │
│  └─────────────────────┘                     └─────────────────────┘                           │
│                                                                                                 │
│  用户电脑B (李四)                           用户电脑C (王五)                                   │
│  ┌─────────────────────┐                     ┌─────────────────────┐                           │
│  │   文件存储           │                     │   文件存储           │                           │
│  │   - 李四经办的项目   │                     │   - 王五经办的项目   │                           │
│  │   - 流程文件         │                     │   - 流程文件         │                           │
│  │   - 归档文件         │                     │   - 归档文件         │                           │
│  └─────────────────────┘                     └─────────────────────┘                           │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 2.2.2 文件访问流程

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    文件访问流程示意图                                            │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  用户B想查看用户A经办项目的文件：                                                                 │
│                                                                                                 │
│  ┌─────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                   │
│  │ 用户B   │      │  管理员电脑  │      │  数据库     │      │  用户A电脑   │                   │
│  │ 浏览器   │      │  FastAPI    │      │  (元数据)   │      │  文件共享    │                   │
│  └────┬────┘      └──────┬──────┘      └──────┬──────┘      └──────┬──────┘                   │
│       │                  │                    │                    │                           │
│       │ 1.请求文件       │                    │                    │                           │
│       │─────────────────►│                    │                    │                           │
│       │                  │ 2.查询文件位置     │                    │                           │
│       │                  │───────────────────►│                    │                           │
│       │                  │ 3.返回存储路径     │                    │                           │
│       │                  │◄───────────────────│                    │                           │
│       │                  │ (用户A电脑IP+路径)  │                    │                           │
│       │                  │                    │                    │                           │
│       │                  │ 4.代理请求文件     │                    │                           │
│       │                  │─────────────────────────────────────────►│                           │
│       │                  │                    │                    │ 5.读取文件                │
│       │                  │                    │                    │───────►                   │
│       │                  │                    │                    │◄───────                   │
│       │                  │ 6.返回文件流       │                    │                           │
│       │                  │◄─────────────────────────────────────────│                           │
│       │ 7.返回文件       │                    │                    │                           │
│       │◄─────────────────│                    │                    │                           │
│       │                  │                    │                    │                           │
│  └─────────┘      └─────────────┘      └─────────────┘      └─────────────┘                   │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 技术栈选型

#### 2.3.1 前端技术栈（不变）

| 技术 | 版本 | 选型理由 | 官方文档 |
|------|------|----------|----------|
| **Vue.js** | 3.4.x | 渐进式框架，学习曲线平缓，生态成熟 | https://vuejs.org |
| **Element Plus** | 2.5.x | Vue3专用组件库，组件丰富，文档完善 | https://element-plus.org |
| **Pinia** | 2.1.x | Vue3官方推荐状态管理，比Vuex更简洁 | https://pinia.vuejs.org |
| **Vue Router** | 4.2.x | Vue官方路由，支持懒加载 | https://router.vuejs.org |
| **Axios** | 1.6.x | 成熟的HTTP客户端，支持拦截器 | https://axios-http.com |
| **Vite** | 5.0.x | 快速构建工具，开发体验好 | https://vitejs.dev |
| **TypeScript** | 5.3.x | 类型安全，减少运行时错误 | https://typescriptlang.org |
| **Sass** | 1.69.x | CSS预处理器，支持变量和混合 | https://sass-lang.com |
| **splitpanes** | 3.1.x | 可拖拽分区组件 | https://antoniandre.github.io/splitpanes |

#### 2.3.2 后端技术栈（新增文件代理）

| 技术 | 版本 | 选型理由 | 官方文档 |
|------|------|----------|----------|
| **Python** | 3.11.x | 语法简洁，生态丰富，适合快速开发 | https://python.org |
| **FastAPI** | 0.109.x | 高性能，自动生成API文档，类型安全 | https://fastapi.tiangolo.com |
| **SQLAlchemy** | 2.0.x | 成熟的ORM框架，支持SQLite | https://sqlalchemy.org |
| **Pydantic** | 2.5.x | 数据验证，与FastAPI深度集成 | https://pydantic.dev |
| **python-docx** | 1.1.x | Word文档生成和操作 | https://python-docx.org |
| **python-multipart** | 0.0.6 | 文件上传支持 | https://pypi.org |
| **uvicorn** | 0.27.x | ASGI服务器，运行FastAPI | https://uvicorn.org |
| **passlib** | 1.7.x | 密码加密 | https://passlib.org |
| **python-jose** | 3.3.x | JWT令牌生成和验证 | https://python-jose.org |
| **requests** | 2.31.x | HTTP请求库（文件代理访问） | https://requests.readthedocs.io |
| **smbprotocol** | 1.9.x | SMB协议访问共享文件夹（可选） | https://github.com/jborean93/smbprotocol |

#### 2.3.3 数据库（不变）

| 技术 | 版本 | 选型理由 |
|------|------|----------|
| **SQLite** | 3.44.x | 轻量级，无需单独服务，文件型数据库，适合本地部署 |

#### 2.3.4 新增：用户电脑文件服务

| 技术 | 版本 | 选型理由 |
|------|------|----------|
| **Python Flask/FastAPI** | 轻量级 | 每个用户电脑运行轻量文件服务，提供文件访问接口 |
| **或 SMB共享** | 系统自带 | Windows内置文件共享功能，无需额外服务 |

### 2.4 全链路实时同步架构（PRD 8.23）

#### 2.4.1 架构图

```
┌─────────────────┐     HTTP 指令      ┌──────────────────┐
│   前端 (Vue)     │ ◄─────────────────►│  后端 (FastAPI)   │
│                 │   WebSocket 订阅    │                  │
│  - 声明上下文    │ ◄─────────────────►│  - 事件汇聚       │
│  - 消费事件更新  │    精准推送         │  - 订阅路由       │
└─────────────────┘                    └────────┬─────────┘
                                                 │ HTTP 指令
                                                 ▼
                                        ┌──────────────────┐
                                        │  存储节点         │
                                        │  - 执行文件操作   │
                                        │  - WebSocket 上报 │
                                        └──────────────────┘
```

#### 2.4.2 通信方式

| 通道 | 协议 | 说明 |
|------|------|------|
| 后端 ↔ 前端 | WebSocket | 事件精准推送，按订阅上下文路由 |
| 后端 → 存储节点 | HTTP | 指令下发（文件操作） |
| 存储节点 → 后端 | WebSocket | 事件上报（操作完成后 emit_event） |

#### 2.4.3 事件协议

**事件对象结构**：
```json
{
  "type": "PROJECT_DELETED",
  "payload": { "id": 123, "path": "..." },
  "timestamp": "2026-03-10T12:00:00Z"
}
```

**订阅消息（前端 → 后端）**：
```json
{
  "action": "subscribe",
  "context": {
    "project_id": 123,
    "procurement_id": 456,
    "scope": "procurement_detail"
  }
}
```

**scope 取值**：`project_list` | `procurement_list` | `procurement_detail` | `archive` | `admin`

#### 2.4.4 实施任务

| 阶段 | 任务 | 产出 |
|------|------|------|
| 1 | 定义事件协议 | `events_schema.py`、`event_types.ts` |
| 2 | 后端 WebSocket 服务 | 连接管理、订阅路由、单实例广播 |
| 3 | 存储节点事件上报 | WebSocket 连接、emit_event 调用点 |
| 4 | 后端事件汇聚 | 接收存储节点事件 → 按订阅推送 |
| 5 | 前端 useRealtimeSync | 连接、订阅、按事件类型更新 ref/reactive |
| 6 | 各模块埋点 | CRUD 成功后调用 emit_event |
| 7 | 多实例预留 | 抽象广播层，便于接入 Redis Pub/Sub |

#### 2.4.5 部署演进

- **当前**：单实例部署
- **计划**：多实例 + Redis Pub/Sub 跨实例广播

---

## 三、系统目录结构

### 3.1 项目整体结构

```
shanhai_procurement/                    # 项目根目录
├── backend/                            # 后端代码（管理员电脑）
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI应用入口
│   │   ├── config.py                  # 配置文件
│   │   ├── database.py                # 数据库连接
│   │   ├── models/                    # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── project.py             # 工程项目模型
│   │   │   ├── procurement.py         # 采购项目模型
│   │   │   ├── supplier.py            # 供应商模型
│   │   │   ├── ledger.py              # 台账模型
│   │   │   ├── file.py                # 文件模型（新增存储位置字段）
│   │   │   └── user.py                # 用户模型（新增电脑信息）
│   │   ├── schemas/                   # Pydantic模式
│   │   ├── api/                       # API路由
│   │   │   ├── files.py               # 文件接口（支持代理访问）
│   │   │   └── ...
│   │   ├── services/                  # 业务逻辑
│   │   │   ├── file_service.py        # 文件服务（支持分布式访问）
│   │   │   ├── file_proxy_service.py  # 文件代理服务（新增）
│   │   │   └── ...
│   │   └── utils/
│   ├── database/                      # SQLite数据库文件
│   │   └── shanhai.db
│   ├── word_templates/                # Word模板库（结构见PRD 3.6.1；自有资金下无集团内/外工程）
│   ├── requirements.txt
│   └── run.sh
│
├── frontend/                          # 前端代码（不变）
│   └── ...
│
├── client_agent/                      # 用户电脑代理程序（新增）
│   ├── app/
│   │   ├── main.py                    # 轻量文件服务入口
│   │   ├── config.py                  # 配置（本机IP、共享路径等）
│   │   ├── file_server.py             # 文件访问服务
│   │   └── auth.py                    # 访问认证
│   ├── requirements.txt
│   └── run.bat                        # Windows启动脚本
│
├── docs/                              # 文档
│   ├── PRD.md
│   ├── UI.md
│   └── TECHNICAL.md
│
├── scripts/                           # 部署脚本
│   ├── init_db.py                     # 数据库初始化
│   ├── init_templates.py              # 模板目录初始化（须遵循PRD 3.6.1：自有资金下不创建集团内/外工程）
│   ├── register_client.py             # 注册客户端电脑
│   ├── backup.py                      # 数据备份
│   └── deploy.sh                      # 部署脚本
│
└── README.md
```

### 3.2 文件系统结构（分布式运行时）

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    分布式文件存储结构                                            │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  管理员电脑 (服务器)                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │   shanhai_procurement/                                                                   │   │
│  │   ├── backend/                                                                           │   │
│  │   │   ├── word_templates/          # Word模板库（集中存储，只读）                         │   │
│  │   │   └── database/                # SQLite数据库（集中存储）                             │   │
│  │   └── logs/                        # 系统日志                                            │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                 │
│  用户电脑A (张三 - 经办人)                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │   shanhai_files/                                                                         │   │
│  │   ├── procurement_process/         # 采购流程文件                                        │   │
│  │   │   └── 专机26-01N 办公楼改造工程/                                                      │   │
│  │   │       └── 专机26-01N-混凝土/     # 张三经办的项目                                     │   │
│  │   │           ├── 采购意向公告.docx                                                      │   │
│  │   │           ├── 供应商推荐表.docx                                                      │   │
│  │   │           └── 目录.docx                                                              │   │
│  │   └── archived_file/               # 归档文件                                            │   │
│  │       └── 专机26-01N材料（设备）合同/                                                       │   │
│  │           └── 专机26-01N-材1/        # 张三经办的项目                                     │   │
│  │               ├── 合同扫描件.pdf                                                         │   │
│  │               └── 资质证明.zip                                                           │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│         │                                                                                       │
│         │ 文件服务 (端口: 8001)                                                                 │
│         ▼                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │   client_agent/                                                                          │   │
│  │   └── app/                                                                               │   │
│  │       └── main.py                  # 轻量文件服务，提供文件访问API                        │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                 │
│  用户电脑B (李四 - 经办人)                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │   shanhai_files/                                                                         │   │
│  │   ├── procurement_process/         # 李四经办的项目文件                                   │   │
│  │   └── archived_file/               # 李四经办的项目归档                                   │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│         │                                                                                       │
│         │ 文件服务 (端口: 8001)                                                                 │
│         ▼                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │   client_agent/                                                                          │   │
│  │   └── app/                                                                               │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 四、数据库设计（更新）

### 4.1 用户表更新（新增电脑信息）

```sql
CREATE TABLE t_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT '采购管理员',
    real_name VARCHAR(50),
    phone VARCHAR(20),
    email VARCHAR(100),
    
    -- 新增字段：电脑信息
    computer_name VARCHAR(100),         -- 电脑名称（网络标识）
    computer_ip VARCHAR(50),            -- 电脑IP地址（局域网）
    file_service_port INTEGER DEFAULT 8001,  -- 文件服务端口
    file_share_path VARCHAR(500),       -- 文件共享根路径
    is_online BOOLEAN DEFAULT 0,        -- 是否在线
    last_heartbeat DATETIME,            -- 最后心跳时间
    
    is_active BOOLEAN DEFAULT 1,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_user_username ON t_user(username);
CREATE INDEX idx_user_computer_ip ON t_user(computer_ip);
```

### 4.2 文件表更新（新增存储位置）

```sql
CREATE TABLE t_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    procurement_id INTEGER NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,        -- 相对路径（相对于用户文件共享根路径）
    file_size INTEGER,
    file_type VARCHAR(50),                  -- 合同文件/普通文件
    is_contract BOOLEAN DEFAULT 0,
    print_mode VARCHAR(10) DEFAULT '单面',
    
    -- 新增字段：存储位置
    owner_user_id INTEGER NOT NULL,         -- 文件所有者用户ID（经办人）
    storage_computer_ip VARCHAR(50),        -- 存储电脑IP
    storage_computer_name VARCHAR(100),     -- 存储电脑名称
    storage_path VARCHAR(500),              -- 完整存储路径（用于代理访问）
    
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    upload_by INTEGER,
    
    -- 外键
    FOREIGN KEY (procurement_id) REFERENCES t_procurement(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_user_id) REFERENCES t_user(id),
    FOREIGN KEY (upload_by) REFERENCES t_user(id)
);

-- 索引
CREATE INDEX idx_file_procurement_id ON t_file(procurement_id);
CREATE INDEX idx_file_owner_user_id ON t_file(owner_user_id);
CREATE INDEX idx_file_storage_ip ON t_file(storage_computer_ip);
```

### 4.3 新增：客户端注册表

```sql
CREATE TABLE t_client_registration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    computer_name VARCHAR(100) NOT NULL,
    computer_ip VARCHAR(50) NOT NULL,
    file_service_port INTEGER DEFAULT 8001,
    file_share_path VARCHAR(500) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',    -- active/inactive/offline
    last_heartbeat DATETIME,
    register_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 外键
    FOREIGN KEY (user_id) REFERENCES t_user(id) ON DELETE CASCADE,
    UNIQUE(user_id, computer_name)
);

-- 索引
CREATE INDEX idx_client_user_id ON t_client_registration(user_id);
CREATE INDEX idx_client_status ON t_client_registration(status);
```

---

## 五、API接口设计（更新）

### 5.1 文件接口（支持分布式访问）

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 上传文件 | POST | /api/files/upload | 上传文件到经办人电脑 |
| 获取文件列表 | GET | /api/files | 获取文件列表（含存储位置） |
| 获取文件内容 | GET | /api/files/{id}/content | **代理访问**，从存储电脑获取文件 |
| 预览文件 | GET | /api/files/{id}/preview | **代理访问**，预览文件 |
| 下载文件 | GET | /api/files/{id}/download | **代理访问**，下载文件 |
| 删除文件 | DELETE | /api/files/{id} | 删除文件（从存储电脑） |
| 更新文件信息 | PUT | /api/files/{id} | 更新文件信息 |
| 批量下载 | POST | /api/files/batch-download | 批量下载（支持跨电脑） |

### 5.2 客户端注册接口（新增）

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 注册客户端 | POST | /api/clients/register | 客户端电脑注册到服务器 |
| 心跳上报 | POST | /api/clients/heartbeat | 客户端上报在线状态 |
| 获取客户端列表 | GET | /api/clients | 获取所有注册客户端 |
| 更新客户端信息 | PUT | /api/clients/{id} | 更新客户端信息 |
| 注销客户端 | DELETE | /api/clients/{id} | 注销客户端 |

---

## 六、核心功能实现方案（更新）

### 6.1 客户端文件服务（用户电脑）

#### 6.1.1 轻量文件服务实现

```python
# client_agent/app/main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import requests
import os
from pathlib import Path
from typing import Optional

app = FastAPI(title="山海纳珍录 - 客户端文件服务")

# 配置
class Config:
    SERVER_URL = "http://192.168.1.100:8000"  # 管理员电脑服务器地址
    COMPUTER_NAME = "ZHANGSAN-PC"  # 本机电脑名称
    COMPUTER_IP = "192.168.1.101"  # 本机IP
    FILE_SHARE_ROOT = "D:/shanhai_files"  # 文件共享根路径
    SERVICE_PORT = 8001
    API_KEY = "your-secret-api-key"  # 与服务器共享的密钥

config = Config()

# 认证依赖
async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

@app.post("/register")
async def register_with_server():
    """向服务器注册本机"""
    payload = {
        "computer_name": config.COMPUTER_NAME,
        "computer_ip": config.COMPUTER_IP,
        "file_service_port": config.SERVICE_PORT,
        "file_share_path": config.FILE_SHARE_ROOT,
        "api_key": config.API_KEY
    }
    response = requests.post(f"{config.SERVER_URL}/api/clients/register", json=payload)
    return response.json()

@app.post("/heartbeat")
async def send_heartbeat():
    """向服务器发送心跳"""
    payload = {
        "computer_name": config.COMPUTER_NAME,
        "computer_ip": config.COMPUTER_IP,
        "status": "online"
    }
    response = requests.post(f"{config.SERVER_URL}/api/clients/heartbeat", json=payload)
    return response.json()

@app.get("/files/{file_path:path}")
async def get_file(file_path: str, api_key: str = Depends(verify_api_key)):
    """
    提供文件访问接口
    服务器通过此接口代理访问本机的文件
    """
    full_path = Path(config.FILE_SHARE_ROOT) / file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    if full_path.is_file():
        return FileResponse(str(full_path))
    else:
        raise HTTPException(status_code=400, detail="Not a file")

@app.get("/stream/{file_path:path}")
async def stream_file(file_path: str, api_key: str = Depends(verify_api_key)):
    """
    提供文件流访问（大文件）
    """
    full_path = Path(config.FILE_SHARE_ROOT) / file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    def iterfile():
        with open(full_path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk
    
    return StreamingResponse(iterfile(), media_type="application/octet-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.SERVICE_PORT)
```

#### 6.1.2 客户端启动脚本 (Windows)

```batch
@echo off
REM client_agent/run.bat

echo 启动山海纳珍录客户端文件服务...

:: 创建虚拟环境（首次运行）
if not exist "venv" (
    python -m venv venv
    venv\Scripts\pip install -r requirements.txt
)

:: 激活虚拟环境
call venv\Scripts\activate

:: 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8001

pause
```

### 6.2 服务器文件代理服务（管理员电脑）

#### 6.2.1 文件代理服务实现

```python
# backend/app/services/file_proxy_service.py
import requests
from pathlib import Path
from typing import Optional, Dict
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.file import t_file
from app.models.user import t_user

class FileProxyService:
    """
    文件代理服务
    负责从分布式存储位置获取文件
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.api_key = "your-secret-api-key"  # 与客户端共享的密钥
        self.request_timeout = 30  # 请求超时时间（秒）
    
    def get_file_record(self, file_id: int) -> dict:
        """获取文件记录"""
        file_record = self.db.query(t_file).filter(t_file.c.id == file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        return dict(file_record)
    
    def get_owner_user(self, user_id: int) -> dict:
        """获取文件所有者用户信息"""
        user = self.db.query(t_user).filter(t_user.c.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(user)
    
    def check_owner_online(self, user: dict) -> bool:
        """检查文件所有者电脑是否在线"""
        # 检查最后心跳时间（5分钟内视为在线）
        from datetime import datetime, timedelta
        if user.get('last_heartbeat'):
            last_heartbeat = datetime.fromisoformat(user['last_heartbeat'])
            if datetime.now() - last_heartbeat < timedelta(minutes=5):
                return True
        return False
    
    def proxy_file_download(self, file_id: int):
        """
        代理文件下载
        从存储电脑获取文件并返回给请求者
        """
        # 获取文件记录
        file_record = self.get_file_record(file_id)
        
        # 获取所有者用户信息
        owner = self.get_owner_user(file_record['owner_user_id'])
        
        # 检查所有者是否在线
        if not self.check_owner_online(owner):
            # 离线时尝试直接访问（可能仍可达）
            pass
        
        # 构建客户端文件服务URL
        client_url = f"http://{owner['computer_ip']}:{owner['file_service_port']}"
        file_path = file_record['file_path']
        
        # 请求客户端文件服务
        try:
            response = requests.get(
                f"{client_url}/stream/{file_path}",
                headers={"X-API-Key": self.api_key},
                timeout=self.request_timeout,
                stream=True
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found on storage computer")
            
            response.raise_for_status()
            
            # 返回文件流
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                response.iter_content(chunk_size=8192),
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{file_record["file_name"]}"'
                }
            )
            
        except requests.exceptions.ConnectionError:
            raise HTTPException(
                status_code=503,
                detail=f"Storage computer ({owner['computer_name']}) is not reachable"
            )
        except requests.exceptions.Timeout:
            raise HTTPException(
                status_code=504,
                detail="File request timeout"
            )
    
    def proxy_file_preview(self, file_id: int):
        """
        代理文件预览
        """
        file_record = self.get_file_record(file_id)
        owner = self.get_owner_user(file_record['owner_user_id'])
        
        client_url = f"http://{owner['computer_ip']}:{owner['file_service_port']}"
        file_path = file_record['file_path']
        
        try:
            response = requests.get(
                f"{client_url}/files/{file_path}",
                headers={"X-API-Key": self.api_key},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            
            # 根据文件类型返回
            from fastapi.responses import Response
            return Response(
                content=response.content,
                media_type=self._get_media_type(file_record['file_name'])
            )
            
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=str(e))
    
    def _get_media_type(self, filename: str) -> str:
        """根据文件扩展名获取MIME类型"""
        from mimetypes import guess_type
        media_type, _ = guess_type(filename)
        return media_type or "application/octet-stream"
    
    def upload_file_to_owner(self, file_content: bytes, file_record: dict, owner: dict):
        """
        上传文件到所有者电脑
        """
        client_url = f"http://{owner['computer_ip']}:{owner['file_service_port']}"
        file_path = file_record['file_path']
        
        files = {'file': (file_record['file_name'], file_content)}
        
        try:
            response = requests.put(
                f"{client_url}/files/{file_path}",
                files=files,
                headers={"X-API-Key": self.api_key},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Failed to upload to storage: {str(e)}")
```

#### 6.2.2 文件API接口更新

```python
# backend/app/api/files.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.file_proxy_service import FileProxyService
from app.core.security import get_current_user

router = APIRouter(prefix="/api/files", tags=["files"])

@router.get("/{file_id}/content")
async def get_file_content(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    获取文件内容（代理访问）
    所有用户都可以访问，系统会自动路由到存储电脑
    """
    proxy_service = FileProxyService(db)
    return proxy_service.proxy_file_download(file_id)

@router.get("/{file_id}/preview")
async def preview_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    预览文件（代理访问）
    """
    proxy_service = FileProxyService(db)
    return proxy_service.proxy_file_preview(file_id)

@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    下载文件（代理访问）
    """
    proxy_service = FileProxyService(db)
    return proxy_service.proxy_file_download(file_id)

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    procurement_id: int = ...,
    is_contract: bool = False,
    print_mode: str = '单面',
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    上传文件
    文件存储到当前用户（经办人之一）的电脑
    """
    from app.services.file_service import FileService
    
    # 读取文件内容
    file_content = await file.read()
    
    # 获取采购项目信息，校验经办人权限
    procurement = db.query(t_procurement).filter(t_procurement.c.id == procurement_id).first()
    project = db.query(t_project).filter(t_project.c.id == procurement.project_id).first()
    
    # 工程项目支持多个经办人：project.officers（示意字段，可为JSON数组或分隔字符串）
    officers = project.officers
    if not user_is_project_officer(current_user, officers) and current_user.get("role") != "系统管理员":
        raise HTTPException(status_code=403, detail="No permission to upload for this project")

    # 文件默认存储在“当前上传者”的电脑（当前用户必须是经办人之一）
    owner_user = db.query(t_user).filter(t_user.c.id == current_user["id"]).first()
    if not owner_user:
        raise HTTPException(status_code=404, detail="Current user not found")
    
    # 创建文件记录
    file_record = {
        'procurement_id': procurement_id,
        'file_name': file.filename,
        'file_path': f"archived_file/{project.engineering_no}材料（设备）合同/{procurement.contract_number}/{file.filename}",
        'file_type': '合同文件' if is_contract else '普通文件',
        'file_size': len(file_content),
        'is_contract': is_contract,
        'print_mode': print_mode,
        'owner_user_id': owner_user.id,
        'storage_computer_ip': owner_user.computer_ip,
        'storage_computer_name': owner_user.computer_name,
        'storage_path': f"{owner_user.file_share_path}/{file_record['file_path']}",
        'upload_by': current_user['id']
    }
    
    # 保存文件记录到数据库
    saved_file = save_file_record(db, file_record)
    
    # 上传文件到经办人电脑
    proxy_service = FileProxyService(db)
    proxy_service.upload_file_to_owner(file_content, file_record, owner_user)
    
    return saved_file
```

### 6.3 客户端注册与心跳

#### 6.3.1 客户端注册接口

```python
# backend/app/api/clients.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import t_user
from app.models.client import t_client_registration
from datetime import datetime

router = APIRouter(prefix="/api/clients", tags=["clients"])

@router.post("/register")
async def register_client(
    client_data: ClientRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    客户端电脑注册
    """
    # 验证API密钥
    if client_data.api_key != SERVER_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # 查找对应用户
    user = db.query(t_user).filter(
        t_user.c.computer_name == client_data.computer_name
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 更新或创建客户端注册记录
    existing = db.query(t_client_registration).filter(
        t_client_registration.c.user_id == user.id,
        t_client_registration.c.computer_name == client_data.computer_name
    ).first()
    
    if existing:
        db.execute(
            t_client_registration.update().where(
                t_client_registration.c.id == existing.id
            ).values(
                computer_ip=client_data.computer_ip,
                file_service_port=client_data.file_service_port,
                file_share_path=client_data.file_share_path,
                status='active',
                last_heartbeat=datetime.now(),
                update_time=datetime.now()
            )
        )
    else:
        db.execute(
            t_client_registration.insert().values(
                user_id=user.id,
                computer_name=client_data.computer_name,
                computer_ip=client_data.computer_ip,
                file_service_port=client_data.file_service_port,
                file_share_path=client_data.file_share_path,
                status='active',
                last_heartbeat=datetime.now()
            )
        )
    
    # 更新用户表
    db.execute(
        t_user.update().where(t_user.c.id == user.id).values(
            computer_ip=client_data.computer_ip,
            file_service_port=client_data.file_service_port,
            file_share_path=client_data.file_share_path,
            is_online=True,
            last_heartbeat=datetime.now()
        )
    )
    
    db.commit()
    
    return {"status": "success", "message": "Client registered"}

@router.post("/heartbeat")
async def client_heartbeat(
    heartbeat_data: HeartbeatRequest,
    db: Session = Depends(get_db)
):
    """
    客户端心跳上报
    """
    user = db.query(t_user).filter(
        t_user.c.computer_name == heartbeat_data.computer_name,
        t_user.c.computer_ip == heartbeat_data.computer_ip
    ).first()
    
    if user:
        db.execute(
            t_user.update().where(t_user.c.id == user.id).values(
                is_online=True,
                last_heartbeat=datetime.now()
            )
        )
        db.commit()
    
    return {"status": "success"}
```

---

## 七、部署方案（更新）

### 7.1 部署架构

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    分布式部署架构                                                │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  管理员电脑 (服务器)                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  IP: 192.168.1.100                                                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  Nginx (端口: 80)                                                                │   │   │
│  │  │  - 反向代理到后端API                                                             │   │   │
│  │  │  - 静态文件服务（前端）                                                          │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘   │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  FastAPI (端口: 8000)                                                            │   │   │
│  │  │  - 业务逻辑                                                                      │   │   │
│  │  │  - 数据库访问                                                                    │   │   │
│  │  │  - 文件代理访问                                                                  │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘   │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  SQLite 数据库                                                                   │   │   │
│  │  │  - 所有元数据                                                                    │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘   │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐   │   │
│  │  │  Word模板库                                                                      │   │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                    ▲                                                            │
│                                    │ 局域网访问                                                 │
│                                    │                                                            │
│  ┌───────────────┬─────────────────┼─────────────────┬───────────────┐                          │
│  │               │                 │                 │               │                          │
│  ▼               ▼                 ▼                 ▼               ▼                          │
│ ┌─────┐       ┌─────┐         ┌─────┐         ┌─────┐       ┌─────┐                            │
│ │用户A│       │用户B│         │用户C│         │用户D│       │用户E│                            │
│ │电脑  │       │电脑  │         │电脑  │         │电脑  │       │电脑  │                            │
│ │192. │       │192. │         │192. │         │192. │       │192. │                            │
│ │168. │       │168. │         │168. │         │168. │       │168. │                            │
│ │1.101│       │1.102│         │1.103│         │1.104│       │1.105│                            │
│ └──┬──┘       └──┬──┘         └──┬──┘         └──┬──┘       └──┬──┘                            │
│    │             │               │               │             │                                │
│    │ 文件服务     │ 文件服务       │ 文件服务       │ 文件服务     │ 文件服务                        │
│    │ 端口:8001   │ 端口:8001     │ 端口:8001     │ 端口:8001   │ 端口:8001                      │
│    │             │               │               │             │                                │
│    ▼             ▼               ▼               ▼             ▼                                │
│ ┌─────────────────────────────────────────────────────────────────────────────────────────┐    │
│ │  各用户电脑文件存储                                                                       │    │
│ │  - 只存储自己经办的项目文件                                                               │    │
│ │  - 通过文件服务提供局域网访问                                                             │    │
│ └─────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 管理员电脑部署步骤

```bash
# 1. 安装Python 3.11
# 2. 安装Node.js 20.x

# 3. 后端部署
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 4. 初始化数据库
python scripts/init_db.py

# 5. 启动后端服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 6. 前端部署
cd ../frontend
npm install
npm run build

# 7. 配置Nginx，指向后端和前端
# 8. 启动Nginx
```

### 7.3 用户电脑部署步骤

```bash
# 1. 安装Python 3.11

# 2. 创建文件存储目录
mkdir D:\shanhai_files
mkdir D:\shanhai_files\procurement_process
mkdir D:\shanhai_files\archived_file

# 3. 部署客户端代理
cd client_agent
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 4. 配置文件
# 编辑 client_agent/app/config.py
# 设置 SERVER_URL = "http://192.168.1.100:8000"  # 管理员电脑IP
# 设置 COMPUTER_NAME = "本机电脑名称"
# 设置 COMPUTER_IP = "本机局域网IP"
# 设置 FILE_SHARE_ROOT = "D:/shanhai_files"

# 5. 注册到服务器
python app/main.py register

# 6. 启动文件服务
uvicorn app.main:app --host 0.0.0.0 --port 8001

# 7. 设置开机自启动（可选）
# 将run.bat添加到启动文件夹
```

### 7.4 客户端注册脚本

```python
# scripts/register_client.py
import requests
import socket
import sys

def get_local_ip():
    """获取本机局域网IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.168.1.1', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def get_computer_name():
    """获取电脑名称"""
    return socket.gethostname()

def register_client(server_url: str, api_key: str, file_share_path: str):
    """注册客户端到服务器"""
    payload = {
        "computer_name": get_computer_name(),
        "computer_ip": get_local_ip(),
        "file_service_port": 8001,
        "file_share_path": file_share_path,
        "api_key": api_key
    }
    
    response = requests.post(f"{server_url}/api/clients/register", json=payload)
    
    if response.status_code == 200:
        print("✓ 注册成功")
        print(f"  电脑名称：{payload['computer_name']}")
        print(f"  电脑IP: {payload['computer_ip']}")
        print(f"  文件路径：{payload['file_share_path']}")
    else:
        print(f"✗ 注册失败：{response.text}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("用法：python register_client.py <服务器URL> <API密钥> <文件共享路径>")
        print("示例：python register_client.py http://192.168.1.100:8000 your-api-key D:/shanhai_files")
        sys.exit(1)
    
    register_client(sys.argv[1], sys.argv[2], sys.argv[3])
```

---

## 八、容错与备份方案

### 8.1 离线访问处理

```python
# backend/app/services/file_proxy_service.py

class FileProxyService:
    # ... (前面的代码)
    
    def handle_offline_owner(self, file_record: dict) -> dict:
        """
        处理文件所有者离线情况
        提供备选方案
        """
        # 方案1：检查是否有备份副本
        backup = self.check_backup_copy(file_record['id'])
        if backup:
            return self.serve_from_backup(backup)
        
        # 方案2：检查是否有其他用户缓存
        cached = self.check_user_cache(file_record['id'])
        if cached:
            return self.serve_from_cache(cached)
        
        # 方案3：返回错误，提示联系文件所有者
        raise HTTPException(
            status_code=503,
            detail=f"文件所有者电脑离线，请联系 {file_record['owner_name']} 获取文件"
        )
    
    def check_backup_copy(self, file_id: int) -> Optional[dict]:
        """检查是否有备份副本"""
        # 查询备份表
        backup = self.db.query(t_file_backup).filter(
            t_file_backup.c.original_file_id == file_id
        ).first()
        return backup
    
    def create_backup_on_upload(self, file_record: dict, file_content: bytes):
        """
        上传时创建备份副本（可选）
        备份到服务器或指定备份位置
        """
        backup_path = f"backups/{file_record['id']}_{file_record['file_name']}"
        # 保存备份
        save_backup(backup_path, file_content)
        
        # 记录备份信息
        self.db.execute(t_file_backup.insert().values(
            original_file_id=file_record['id'],
            backup_path=backup_path,
            backup_time=datetime.now()
        ))
        self.db.commit()
```

### 8.2 数据备份策略

```python
# scripts/backup.py
import shutil
import datetime
from pathlib import Path
import requests

class BackupManager:
    def __init__(self, server_url: str, api_key: str):
        self.server_url = server_url
        self.api_key = api_key
        self.backup_root = Path("backups")
    
    def full_backup(self):
        """完整备份"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.backup_root / f"full_backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 备份数据库
        db_path = Path('backend/database/shanhai.db')
        if db_path.exists():
            shutil.copy2(db_path, backup_dir / 'shanhai.db')
        
        # 2. 备份Word模板
        template_path = Path('backend/word_templates')
        if template_path.exists():
            shutil.copytree(template_path, backup_dir / 'word_templates')
        
        # 3. 从各客户端备份文件（可选）
        self.backup_client_files(backup_dir)
        
        print(f"完整备份完成：{backup_dir}")
        return backup_dir
    
    def backup_client_files(self, backup_dir: str):
        """从各客户端备份文件"""
        # 获取所有客户端列表
        clients = self.get_client_list()
        
        for client in clients:
            client_backup_dir = backup_dir / f"client_{client['computer_name']}"
            client_backup_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                # 请求客户端备份文件列表
                response = requests.get(
                    f"http://{client['computer_ip']}:{client['file_service_port']}/backup-list",
                    headers={"X-API-Key": self.api_key},
                    timeout=60
                )
                
                if response.status_code == 200:
                    file_list = response.json()
                    # 下载文件
                    for file_info in file_list:
                        self.download_client_file(
                            client,
                            file_info['path'],
                            client_backup_dir
                        )
            except Exception as e:
                print(f"备份客户端 {client['computer_name']} 失败：{e}")
    
    def get_client_list(self):
        """获取客户端列表"""
        response = requests.get(
            f"{self.server_url}/api/clients",
            headers={"X-API-Key": self.api_key}
        )
        return response.json()
```

### 8.3 客户端离线处理流程

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    客户端离线处理流程                                            │
├─────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                 │
│  用户B想访问用户A经办项目的文件，但用户A电脑离线：                                                 │
│                                                                                                 │
│  ┌─────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                   │
│  │ 用户B   │      │  管理员电脑  │      │  数据库     │      │  用户A电脑   │                   │
│  │ 浏览器   │      │  FastAPI    │      │  (元数据)   │      │  (离线)     │                   │
│  └────┬────┘      └──────┬──────┘      └──────┬──────┘      └──────┬──────┘                   │
│       │                  │                    │                    │                           │
│       │ 1.请求文件       │                    │                    │                           │
│       │─────────────────►│                    │                    │                           │
│       │                  │ 2.查询文件位置     │                    │                           │
│       │                  │───────────────────►│                    │                           │
│       │                  │ 3.返回存储位置     │                    │                           │
│       │                  │◄───────────────────│                    │                           │
│       │                  │ (用户A电脑，离线)   │                    │                           │
│       │                  │                    │                    │                           │
│       │                  │ 4.尝试访问用户A    │                    │                           │
│       │                  │─────────────────────────────────────────►│                           │
│       │                  │                    │                    │ ✗ 无法连接                │
│       │                  │                    │                    │                           │
│       │                  │ 5.检查备份副本     │                    │                           │
│       │                  │───────────────────►│                    │                           │
│       │                  │ 6.有备份？         │                    │                           │
│       │                  │◄───────────────────│                    │                           │
│       │                  │                    │                    │                           │
│       │                  │ ┌───────┐         │                    │                           │
│       │                  │ │  是   │─────────┼────┐               │                           │
│       │                  │ └───────┘         │    │ 7.从备份返回   │                           │
│       │                  │     │             │    │───────────────►│                           │
│       │                  │     │             │    │                │                           │
│       │                  │     ▼             │    │                │                           │
│       │                  │ ┌───────┐         │    │                │                           │
│       │                  │ │  否   │─────────┼────┘                │                           │
│       │                  │ └───────┘         │                     │                           │
│       │                  │     │             │                     │                           │
│       │                  │     ▼             │                     │                           │
│       │                  │ 8.返回错误提示    │                     │                           │
│       │ 9.提示联系用户A  │◄──────────────────│                     │                           │
│       │◄─────────────────│                    │                    │                           │
│       │                  │                    │                    │                           │
│  └─────────┘      └─────────────┘      └─────────────┘      └─────────────┘                   │
│                                                                                                 │
│  建议方案：                                                                                     │
│  1. 重要文件自动备份到服务器（可配置）                                                           │
│  2. 定期同步文件到备份服务器                                                                     │
│  3. 离线时提示联系文件所有者                                                                     │
│                                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 九、安全与权限

### 9.1 访问权限控制

| 操作 | 经办人 | 其他组员 | 系统管理员 |
|------|--------|----------|------------|
| 查看项目信息 | ✓ | ✓ | ✓ |
| 查看流程文件 | ✓ | ✓ | ✓ |
| 查看归档文件 | ✓ | ✓ | ✓ |
| 下载/复制文件 | ✓ | ✓ | ✓ |
| 上传文件 | ✓ | ✗ | ✓ |
| 删除文件 | ✓ | ✗ | ✓ |
| 编辑项目信息 | ✓ | ✗ | ✓ |

> **口径说明（与PRD一致）**：此处“经办人”指 **工程项目字段“材料（设备）采购经办人（可多选）”列表中的任意一位用户**。只要当前用户属于该列表，即视为拥有经办权限。

### 9.2 文件访问认证

```python
# 所有文件访问请求需要：
# 1. 有效的用户登录token
# 2. 客户端服务API密钥验证

# 服务器→客户端文件服务请求
headers = {
    "X-API-Key": SERVER_API_KEY,  # 服务器与客户端共享密钥
    "Authorization": f"Bearer {user_token}"  # 用户登录token
}
```

---

## 十、依赖清单（更新）

### 10.1 后端依赖 (backend/requirements.txt)

```
fastapi==0.109.0
uvicorn==0.27.0
sqlalchemy==2.0.25
pydantic==2.5.3
python-jose==3.3.0
passlib==1.7.4
python-multipart==0.0.6
python-docx==1.1.0
openpyxl==3.1.2
aiofiles==23.2.1
bcrypt==4.1.2
requests==2.31.0
```

### 10.2 客户端依赖 (client_agent/requirements.txt)

```
fastapi==0.109.0
uvicorn==0.27.0
python-multipart==0.0.6
requests==2.31.0
```

### 10.3 前端依赖 (frontend/package.json)

```json
{
  "dependencies": {
    "vue": "^3.4.15",
    "vue-router": "^4.2.5",
    "pinia": "^2.1.7",
    "element-plus": "^2.5.4",
    "axios": "^1.6.5",
    "splitpanes": "^3.1.5",
    "@element-plus/icons-vue": "^2.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.3",
    "vite": "^5.0.11",
    "typescript": "^5.3.3",
    "sass": "^1.69.7",
    "unplugin-auto-import": "^0.17.4",
    "unplugin-vue-components": "^0.26.0"
  }
}
```

---

## 十一、常见问题解答

### Q1: 用户电脑关机后，其他用户如何访问文件？

**A:** 有三种方案：
1. **推荐**：重要文件自动备份到服务器，离线时从备份获取
2. **可选**：设置定期同步，将文件同步到备份服务器
3. **临时**：联系文件所有者开机后访问

### Q2: 如何确保文件服务开机自启动？

**A:** 
- Windows：将启动脚本添加到"启动"文件夹或使用任务计划程序
- 配置为Windows服务（使用nssm或类似工具）

### Q3: 网络中断怎么办？

**A:**
- 局域网内访问不受影响
- 系统会检测客户端在线状态，离线时给出提示
- 可查看元数据信息，文件访问需等待网络恢复

### Q4: 文件存储分散，如何统一管理？

**A:**
- 所有文件元数据集中在服务器数据库
- 通过文件代理服务统一访问接口
- 定期备份脚本可汇总所有文件

---

**文档版本：v2.0（分布式文件存储版）**
**创建日期：2026-03-09**
**文档状态：✅ 已完成**