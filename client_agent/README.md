# 客户端文件服务（client_agent）

主后端从本机拉取合同等文件时，会请求 **`http://<本机IP>:8001/stream/...`**，因此本机需常驻运行本服务（默认端口 **8001**，与主后端 **8000** 不同）。

## 启动方式

- **推荐**：双击或在 `client_agent` 目录下执行 **`run.bat`**
- 手动：`call venv\Scripts\activate.bat` → `pip install -r requirements.txt` → `uvicorn app.main:app --host 0.0.0.0 --port 8001`

> 在 **cmd** 里必须用 **`call venv\Scripts\activate.bat`**，不要只输入 `venv\Scripts\activate`。

---

## 创建 venv 卡住、Ctrl+C 也退不出？

这是 **Windows 上常见问题**，多半不是代码写错，而是环境在「大量拷文件」时被拖慢或锁住。

### 原因说明

| 情况 | 说明 |
|------|------|
| **Windows Defender / 杀毒** | 对 `venv` 里成千上万个小文件实时扫描，会极慢，看起来像死机；中断信号有时要等很久才生效。 |
| **项目目录在云盘同步** | 若工程在 OneDrive、坚果云、iCloud 等同步目录下，创建 venv 会频繁锁文件，容易卡死。 |
| **Python 版本过新** | 例如 **3.14** 等刚发布的版本，偶发与 `venv` 工具链不兼容或明显变慢，可换 **3.11 / 3.12** 再试。 |
| **上次中断留下半成品** | 删到一半的 `venv` 文件夹可能导致再次创建异常。 |

### 建议操作（按顺序试）

1. **结束卡住的进程**  
   Ctrl+C 若无效：打开 **任务管理器**，结束所有 **`python.exe`**，再删文件夹（见下一条）。

2. **删掉不完整的 venv 再建**  
   关闭所有占用该目录的终端，删除整个 **`client_agent\venv`** 文件夹后重试。

3. **给目录加杀毒排除（最有效）**  
   在 Windows 安全中心 → 病毒和威胁防护 → 管理设置 → 排除项中，添加：  
   `D:\ShanHaiNaZhen_system\client_agent`  
   （路径按你实际盘符调整。）

4. **把 venv 建到用户目录（避开云盘与工程目录）**  
   使用仓库里的 **`setup_venv_userprofile.bat`** 创建虚拟环境，再用 **`run_user_venv.bat`** 启动（见同目录脚本说明）。

5. **指定稳定版 Python**  
   ```bat
   py -3.12 -m venv venv
   ```
   若已装多版本 Python，用 `py -0` 查看列表。

6. **耐心等待**  
   在机械硬盘 + 杀毒全开时，**首次创建 venv 等 5～10 分钟** 仍有可能，属正常现象；加排除项后通常会快很多。

---

## 与后端的配合

- 后端环境变量 **`CLIENT_API_KEY`** 须与 `client_agent/app/config.py` 里的 **`API_KEY`** 一致（默认多为 `your-secret-api-key`，生产请双方同时改掉）。
- 用户资料里填写的 **本机 IP、文件服务端口** 需与真实监听地址一致，否则主后端会报「存储电脑不可达」。
- **`FILE_SHARE_ROOT`（默认 `D:/shanhai_files`）** 必须与后端 **`ARCHIVED_FILE_ROOT`**（默认 `backend/data/archived_file`）指向**同一套物理目录**，否则 8001 会 **404**，主端可能报 **HTTP 500**。单机开发示例（按你的盘符改）：
  ```bat
  set FILE_SHARE_ROOT=D:\ShanHaiNaZhen_system\backend\data\archived_file
  uvicorn app.main:app --host 0.0.0.0 --port 8001
  ```
  若文件已落盘在后端归档目录，主后端已支持 **优先读本地**，可不启 8001 也能预览；若仍走代理，则必须对齐上述根目录。
