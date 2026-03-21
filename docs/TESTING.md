# 测试说明（自动化 + 试运行）

## 1. 后端接口自动化（pytest）

使用**独立临时 SQLite**，不会修改 `backend/database/shanhai.db`。

```bash
cd backend
venv\Scripts\activate
pip install -r requirements-dev.txt
pytest tests -q
```

覆盖范围（持续可扩展）：

- 根路由、`/api/health`、`/api/stats`
- 登录失败 / `me` 鉴权
- 工程列表、创建工程、**有采购时禁止删除工程**、无采购时可删
- 工程导出 Excel：未勾选 ID 时 400
- 台账列表（已登录，响应含 `items` / `total`）

## 2. 对已启动后端的 HTTP 冒烟

先启动 `uvicorn`，再在项目根目录：

```bash
python scripts/smoke_http.py
```

可选环境变量：`SHANHAI_API_BASE`（默认 `http://127.0.0.1:8000`）。

## 3. 数据库种子数据（功能遍历）

**轻量示例（少量采购）：**

```bash
python scripts/init_db.py
backend\venv\Scripts\python.exe scripts\seed_test_data.py
```

**按模板大批量（3 工程 × 每工程 60 条采购，含五选二与多轮补充协议）：**

```bash
# 首次或要覆盖同名工程时加 --clear（删除 专土23-07 / 专机23-17N / 日常25-21）
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear

# 仅删除上述三个工程、不重新灌数：加 --clear-only
# 可选：--process-files-count N（默认 50）随机 N 条采购拷贝 Word 模板目录下全部 .docx 到流程文件夹；--no-process-files 关闭
# 可选：--seed 整数 固定随机抽样，便于复现
```

脚本还会在**已存在的三个模板工程**下：为**每条采购**在正式归档目录落一份「占位归档合同」PDF（已有则跳过），并按与上传归档一致的规则**生成台账**；并默认随机 **50** 条采购写入全套流程 docx（依赖系统设置中的模板目录，若无模板则仅写 `目录.docx` 占位）。

数据来源：`docs/seed_data_template.md`；脚本：`scripts/seed_from_template.py`。**逐步操作、参数说明、目录与环境变量**见 [seed_from_template_guide.md](seed_from_template_guide.md)。

详见 `scripts/seed_test_data.py` 顶部说明。定制字段请填 **`docs/seed_data_template.md`**。

## 4. 仅你能做的界面与业务测试

见 **`docs/UAT-manual-phases.md`**（分阶段、分轻重）。

## 5. 环境变量（可选）

| 变量 | 说明 |
|------|------|
| `SHANHAI_DATABASE_PATH` | SQLite 文件路径（pytest conftest 会自动设临时文件） |
| `PROCUREMENT_PROCESS_ROOT` / `ARCHIVED_FILE_ROOT` | 流程与归档根目录 |
