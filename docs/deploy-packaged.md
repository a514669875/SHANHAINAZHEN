# 封装版部署说明（办公室单机服务 + 浏览器）

> 目标：**一台 Windows 电脑**运行后端（**8000**）后，全员用浏览器访问 **同一地址**。数据库与所有生成/归档文件均在 **该服务器本机 `backend\data`**。  
> **从家里拷 U 盘到公司、为啥没有安装包**：请看 **[小白操作说明](./小白操作说明.md)** 中的 **「七、打包和搬运文件」**。

---

## 1. 与开发模式的区别

| 项目 | 开发 | 封装/生产 |
|------|------|-----------|
| 前端 | `npm run dev`（5173）+ Vite 代理 | **不必**装 Node；静态文件由 **8000** 一并提供 |
| 启动 | 两个终端 | 服务端通常 **一个** `scripts\start_production.bat` |
| 访问 | localhost:5173 | `http://服务器IP:8000` |

后端会按以下顺序查找前端构建目录（**任一路径存在 `index.html` 即启用网页**）：

1. 环境变量 **`SHANHAI_STATIC_DIST`**
2. **`backend/web/dist`**（推荐：拷贝后的单目录分发）
3. **`frontend/dist`**（开发机构建后直接启动）

---

## 2. 首次准备（在「服务端」电脑上）

1. 安装 **Python 3.11+**（勾选 Add to PATH）。
2. 将完整项目（或你们的发布包）放到固定目录，例如 `D:\ShanHaiNaZhen_system`。
3. 创建后端虚拟环境（若发布包已带 `backend\venv` 可跳过）：
   ```bat
   cd D:\ShanHaiNaZhen_system\backend
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. 初始化数据库（仅首次）：
   ```bat
   cd D:\ShanHaiNaZhen_system
   backend\venv\Scripts\python.exe scripts\init_db.py
   ```
5. **构建前端**（在装了 Node 的机器上执行一次后，把产物拷到服务器亦可）：
   ```bat
   cd D:\ShanHaiNaZhen_system
   scripts\build_package_assets.bat
   ```
6. **（推荐）** 同步到 `backend\web\dist`，便于以后只备份/替换 `backend` 目录：
   ```bat
   scripts\sync_dist_to_backend_web.bat
   ```
7. 根目录 **`VERSION.txt`** 第一行为对外版本号；发版时修改此处即可。

---

## 3. 日常启动（服务端）

双击或在项目根目录执行：

```bat
scripts\start_production.bat
```

- 本机浏览器打开：**http://127.0.0.1:8000**
- 同事电脑：**http://这台服务器的IPv4:8000**（需同一局域网，防火墙放行 8000）

若窗口提示 **Serving SPA static files from ...** 说明网页已挂载成功；若无该行且打开根地址是 JSON，说明未找到 `dist`，请检查第 2 步构建与路径。

---

## 4. 同事电脑还需要装什么？

- **不需要**。只要服务器已按第 3 节启动 **8000**，同事 **Chrome/Edge 访问 `http://服务器IP:8000`** 即可。

---

## 5. 升级与备份

1. **升级前**：在项目根目录执行 `python scripts\backup.py`。
2. 用新版本**覆盖**程序文件；**保留** `backend\database\`、`backend\data\` 等数据目录。
3. 若发版说明要求执行迁移：  
   `backend\venv\Scripts\python.exe scripts\migrate_add_columns.py`
4. 若前端有更新：重新执行 **`build_package_assets.bat`** 与（建议）**`sync_dist_to_backend_web.bat`**。

---

## 6. 安全建议（生产）

- 修改默认管理员密码；生产环境务必设置 **`SECRET_KEY`**。
- 仅内网访问；如需公网务必使用 HTTPS 与专业网关，不在此文档范围。

---

## 7. 故障速查

| 现象 | 处理 |
|------|------|
| 能打开登录页但接口失败 | 看浏览器 F12 网络；确认访问的是 **8000** 且后端窗口无报错 |
| 只有 `{"message":"山海纳珍录 API"...}` | 未找到 `dist`，按第 2 步构建或设置 `SHANHAI_STATIC_DIST` |
| 合同预览 404 / 文件找不到 | 文件应在 **服务器** `backend\data` 下；确认未误删且备份还原路径一致 |

更多测试清单见 [UAT-manual-phases.md](./UAT-manual-phases.md)、封装清单见 [packaging-readiness.md](./packaging-readiness.md)。
