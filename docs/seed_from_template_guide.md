# 种子脚本 `seed_from_template.py` 详细使用教程

本文说明如何从零开始，用 **`scripts/seed_from_template.py`** 向系统灌入「三个模板工程 + 大批量采购」，以及归档占位、流程 Word 文件等行为。

---

## 一、这个脚本是干什么的？

1. **工程与采购数据**  
   按 `docs/seed_data_template.md` 的约定，写入 **3 个固定工程编号**：
   - `专土23-07`（工程类 · 集团内）
   - `专机23-17N`（工程类 · 集团外）
   - `日常25-21`（自有资金）  

   每个工程约 **60 条采购记录**（模板里 56 条规格，其中 **五选二** 会拆成 2 条库记录）。

2. **归档合同占位（每条采购）**  
   只要数据库里**已经存在**上述任一模板工程，脚本结束时会在 **归档根目录**（见下文环境变量）下，为**尚未有占位文件**的采购各写 **1 个极小 PDF**，并在表 `t_file` 里记一条 **合同文件**。已存在同名占位则**跳过**。

3. **流程文件（默认随机 50 条采购）**  
   从上述模板工程下的**全部采购**里 **随机抽 N 条**（默认 N=50），把 **Word 模板目录**里该采购类型对应的子文件夹下 **所有 `.docx`** 复制到该采购的 **流程文件夹**，并写入/更新流程同步状态。  
   - 若模板目录不存在或为空，仍会在流程目录生成 **`目录.docx`** 占位。

---

## 二、使用前准备

### 1. Python 与虚拟环境

脚本依赖 **backend** 里的包（SQLAlchemy、python-docx 等），请使用已安装 `backend/requirements.txt` 的解释器。

**Windows（推荐）：**

```powershell
cd d:\ShanHaiNaZhen_system
backend\venv\Scripts\python.exe scripts\seed_from_template.py --help
```

若尚未创建 venv：

```powershell
cd d:\ShanHaiNaZhen_system\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 数据库与管理员

必须先执行 **`init_db.py`**，保证存在默认管理员 **`admin`**（脚本里写死了按用户名 `admin` 取 `owner_user_id`）。

```powershell
cd d:\ShanHaiNaZhen_system
python scripts\init_db.py
```

默认管理员一般为：`admin` / `admin123`（以你环境实际为准）。

### 3. 工作目录

请在 **`项目根目录`**（包含 `scripts/`、`backend/` 的目录）下执行命令，例如 `d:\ShanHaiNaZhen_system`。  
脚本内部会把 `backend` 加入 `sys.path`，在别的目录执行可能找不到模块。

---

## 三、命令行参数一览

| 参数 | 作用 |
|------|------|
| `--clear` | 先**删除**库中工程编号为 `专土23-07`、`专机23-17N`、`日常25-21` 的工程（级联删除其采购等），再重新灌数。**首次灌模板数据或要完全重来时用。** |
| `--process-files-count N` | 随机 **N** 条采购做「全套流程 docx」拷贝；**默认 50**；**0** 表示关闭。 |
| `--no-process-files` | 不拷贝流程 docx，等价于 `--process-files-count 0`（仍会写**归档占位**，只要库里有模板工程）。 |
| `--seed 整数` | 固定随机数种子，使「抽哪 N 条采购」**每次一致**，便于复现问题或对比环境。 |

查看帮助：

```powershell
backend\venv\Scripts\python.exe scripts\seed_from_template.py --help
```

---

## 四、推荐操作步骤

### 场景 A：第一次灌入模板大数据（最常用）

会**删掉**三个同名工程（若存在）再重建，适合干净环境或愿意清空这三项测试数据时：

```powershell
cd d:\ShanHaiNaZhen_system
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear
```

执行结束后控制台会提示：
- 本次新建了多少条采购；
- **归档占位**新建了多少条 `File`；
- **流程文件**从多少条采购里抽了多少条、成功写入了多少条。

### 场景 B：三个工程已在库里，只想补占位 / 再抽一批流程文件

**不要**加 `--clear`（否则会删工程）：

```powershell
backend\venv\Scripts\python.exe scripts\seed_from_template.py
```

- 已存在的工程：**不会**重复创建采购（脚本会打印「跳过已存在工程」）。
- 仍会扫描三个模板工程下的采购：**补缺失的归档占位**；并按默认再 **随机 50 条** 拷流程 docx（已存在的文件可能被覆盖，视目录与模板而定）。

### 场景 C：只要数据 + 归档占位，不要流程 Word

```powershell
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear --no-process-files
```

或：

```powershell
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear --process-files-count 0
```

### 场景 D：固定「随机 50 条」是哪 50 条（可复现）

```powershell
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear --seed 42
```

换 `--seed` 会换一批采购；同一 `--seed` 多次执行（在相同数据状态下）抽样一致。

### 场景 E：随机 20 条流程即可

```powershell
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear --process-files-count 20
```

---

## 五、文件与目录会写到哪里？

由 **`backend/app/config.py`** 决定（可通过环境变量覆盖）：

| 含义 | 默认位置 | 环境变量 |
|------|----------|----------|
| SQLite 数据库 | `backend/database/shanhai.db` | `SHANHAI_DATABASE_PATH` |
| 流程文件根目录 | `backend/data/procurement_process` | `PROCUREMENT_PROCESS_ROOT` |
| 归档文件根目录 | `backend/data/archived_file` | `ARCHIVED_FILE_ROOT` |
| Word 模板根目录 | 优先 `backend/data/config.json` 里的 `word_templates_dir`，其次 `WORD_TEMPLATES_DIR`，再否则 `backend/word_templates` | `WORD_TEMPLATES_DIR` 或系统设置里配置 |

**模板路径**：与后端「系统设置 → Word 模板目录」一致；管理员在界面里改过后，`config.json` 会生效，种子脚本与 API 使用同一逻辑。

---

## 六、怎样「一键」清空测试数据？

没有单独的「清空按钮」，按你要清的范围选一种即可。

### 1. 只删模板三大工程（专土23-07 / 专机23-17N / 日常25-21），**不要**重新灌数

一条命令（**不删**库里其它工程、其它用户）：

```powershell
cd d:\ShanHaiNaZhen_system
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear-only
```

`--clear-only`：**仅删除**这三个工程及其级联数据，**不会**再创建工程、采购、占位合同、流程文件或台账。

### 2. 删完再重新灌模板数据（一键重置测试环境）

```powershell
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear
```

`--clear` 会先删上述三个工程，再**立即**按模板重新创建并灌数（含归档占位、台账、随机流程文件等）。与 `--clear-only` 不同，不要搞混。

### 3. 整个业务库重来（所有工程、采购、台账等全部清空）

适用于「开发环境整库还原」：

1. **先停掉**正在跑的后端（避免占用 SQLite）。
2. 删除数据库文件（默认路径）：
   - `backend\database\shanhai.db`  
   若用过环境变量 `SHANHAI_DATABASE_PATH`，则删你指向的那个文件。
3. 再执行：

```powershell
cd d:\ShanHaiNaZhen_system
python scripts\init_db.py
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear
```

`init_db.py` 会建表并确保 `admin` 存在；再按需跑 `seed_test_data.py` 等。

### 4. 磁盘上的流程 / 归档文件

删库**不会**自动删掉 `backend\data\procurement_process`、`backend\data\archived_file`（或你通过环境变量指向的目录）里的历史文件夹。若希望连文件一并干净，可**手动删除**这两个目录下内容（或整目录），再重新跑种子/上传。注意：**先停后端**再删，避免占用。

### 5. 轻量种子 `seed_test_data.py` 的工程

该脚本使用**其它工程编号**（如 `专机26-10N`），**不会**被 `seed_from_template.py --clear` 删掉。要清掉需在界面删除工程，或采用上面「整库重来」。

---

## 七、如何确认成功了？

1. **登录前端**，在工程列表中能看到三个模板工程。  
2. 进入某一工程 → 采购列表，条数应接近每工程 60。  
3. **归档**：在 `ARCHIVED_FILE_ROOT` 下出现 `{工程编号}材料（设备）合同\...` 及占位 PDF。  
4. **流程**：在 `PROCUREMENT_PROCESS_ROOT` 下 `{工程编号} {工程名称}\{工程编号}-{采购内容}\` 中有被抽中的采购对应的 docx（或至少有 `目录.docx`）。  
5. **台账**：前端台账列表中应有与模板采购对应的记录（五选二为两条/对）。

---

## 八、常见问题

### 1. 报错：请先运行 init_db.py 创建管理员用户

先执行 `python scripts/init_db.py`，并确认库里有用户名为 **`admin`** 的用户。

### 2. `ModuleNotFoundError: No module named 'app'`

不要用系统全局 `python` 且未装依赖；请用 **`backend\venv\Scripts\python.exe`**，且在**项目根目录**执行脚本。

### 3. 流程文件只有 `目录.docx`，没有其它 docx

说明 **Word 模板目录**下对应「资金类别 / 工程类别 / 采购类型 / 采购方式」的子路径里没有模板文件。需要在系统设置中配置模板目录，并按 PRD 目录结构放入 `.docx` 后再跑脚本。

### 4. `--clear` / `--clear-only` 会删什么？

- **`--clear-only`**：只删三个模板工程及级联数据，**不**再灌数。  
- **`--clear`**：先同样删掉，再**立刻**按模板重建并灌数。  
二者都**不会**动库里其它工程；也**不会**清空整个数据库。

### 5. 和 `seed_test_data.py` 的区别

- **`seed_test_data.py`**：轻量示例，条数少，适合快速冒烟。  
- **`seed_from_template.py`**：按 `seed_data_template.md` 的大批量模板数据 + 归档占位 + **台账（与归档规则一致）** +（可选）随机流程文件。

### 6. 种子脚本的占位合同与台账

- **当前版本**：在写入「归档占位合同」后，种子脚本会按与 **`try_archive_and_create_ledgers`** 相同的规则**补建台账**（供应商、成交价、补充协议、五选二等逻辑一致），并写入 **`pdf_preview_path`**。
- **五选二**：需 **一标段、二标段** 在归档路径下**各有**一份合同占位后，才会为两段各建一条台账（与正式上传归档条件一致）。
- **界面「上传合同」**：仍走暂存 `_temp` → 归档 → 台账；若你**只**用手动上传、不用种子占位，行为与过去一致。

---

## 九、数据从哪来、怎么改？

- 字段与业务含义：**`docs/seed_data_template.md`**。  
- 脚本里采购条目的具体列表在 **`scripts/seed_from_template.py`** 的 `build_procurement_specs_56()` 等处；改模板文档后若要一致，需同步改脚本或扩展脚本读取逻辑。

---

## 十、一键命令备忘（Windows）

```powershell
cd d:\ShanHaiNaZhen_system
python scripts\init_db.py
backend\venv\Scripts\python.exe scripts\seed_from_template.py --clear
```

需要可复现的 50 条流程抽样时加上：`--seed 42`。
