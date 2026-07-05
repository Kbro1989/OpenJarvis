# Snowflake 入门与接口指南

本指南面向“知道 SQL、但没怎么用过 Snowflake”的用户，目标是少讲概念、多给可执行步骤。
你可以把它当作：从“完全没连上”到“本地脚本/自动化/业务系统都能用”的一条路径。

---


## 第一部分：先理解 Snowflake 的基本结构

连上 Snowflake 之前，先把几个核心概念过一遍。你不需要全记，但看 SQL 时会一直碰到它们。

- **Account**：租户标识，通常长成 `abc12345.us-east-1` 这种形式。
- **Warehouse**：计算资源，执行 SQL 前要先启用。
- **Database / Schema**：两级命名空间。
- **Stage**：文件上传/下载的中转区。
- **Query History / Results**：查询历史与结果通常在 Web UI 里看。

---


## 第二部分：最快捷上手方式 — Snowsight

先验证你能访问账号，再决定后续走哪条路。

### 步骤 1：登录
- 打开：`https://<your-account>.snowflakecomputing.com`
- 用你的账号登录，注意不是邮箱，而是 Snowflake 给的 account + user。

### 步骤 2：写第一条 SQL
- 进入 **Worksheets**
- 执行：
  ```sql
  SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE();
  ```
- 如果能返回结果，就说明账号、权限、网络都没问题。

### 步骤 3：确认 warehouse
默认情况下你可能看不到数据，因为 warehouse 没开。
```sql
SHOW WAREHOUSES;
```
找一个你能用的 warehouse，然后启用：
```sql
USE WAREHOUSE <warehouse_name>;
```

---


## 第三部分：本地开发首选 — Python 连接器

如果你最终要写脚本、做分析、接自动化流程，这一步最实用。

### 安装
```bash
pip install snowflake-connector-python
```

### 最小可运行示例
```python
import snowflake.connector

conn = snowflake.connector.connect(
    account="<your_account>",         # 如：abc12345.us-east-1
    user="<your_user>",
    password="<your_password>",
    warehouse="<warehouse_name>",
    database="<database_name>",
    schema="<schema_name>",
)

cur = conn.cursor()
try:
    cur.execute("SELECT CURRENT_VERSION()")
    print(cur.fetchone()[0])

    cur.execute("SELECT * FROM my_table LIMIT 10")
    for row in cur.fetchall():
        print(row)
finally:
    cur.close()
    conn.close()
```

### 连接参数说明
| 参数 | 说明 |
|------|------|
| `account` | 如 `abc12345.us-east-1`，不含 `https://` |
| `user` | Snowflake 用户名 |
| `password` | 密码；如果开了 MFA，优先用 key pair |
| `warehouse` | 必须先有可用 warehouse |
| `database` | 数据库名 |
| `schema` | Schema 名 |

---


## 第四部分：服务/自动化场景 — REST API

如果你要把 Snowflake 接到其他系统里，比如 Web App、Lambda、定时任务，走 SQL API 更合适。

### Endpoint
```
POST /api/v2/statements
```

### 最小 cURL 示例
```bash
curl -X POST "https://<account>.snowflakecomputing.com/api/v2/statements" \
  -H "Authorization: Bearer <session_token>" \
  -H "Content-Type: application/json" \
  -d '{"statement": "SELECT 1"}'
```

实际工程里更推荐：
- **Python connector**：它会帮你管理 session、重试、结果轮询
- **Snowpark**：如果你要做 DataFrame 级开发

---


## 第五部分：脚本化操作 — Snowflake CLI

适合批处理、定时任务、开发者在终端里快速操作。

### 安装
```bash
pip install snowflake-cli
```

### 常用命令
```bash
# 登录
snow connection login

# 执行 SQL
snow sql -q "SELECT CURRENT_USER()"

# 列出对象
snow object list --like "MY_TABLE"
```

---


## 第六部分：BI / 传统应用 — ODBC / JDBC

如果你要把 Snowflake 接到 Tableau、Power BI、Jupyter、老应用里，用 ODBC 或 JDBC。

- 安装对应驱动
- 按驱动要求配置 account、warehouse、database、schema、user/password 或 key pair
- 在 BI 工具里新建 Snowflake 数据源即可

---


## 第七部分：新手最容易忽略的 5 个点

1. **Warehouse 必须先启用**：连上了账号不等于能跑 SQL。
2. **Account 不要带 `https://`**：连接器只要 account 标识。
3. **默认数据库/ schema 可能不存在**：显式写 `database` 和 `schema` 更稳。
4. **大结果用 fetch_pandas_all()**：不要把所有结果一次拉到内存里。
5. **权限要一层层看**：Account → Warehouse → Database → Schema → Table 都可能受限。

---


## 第八部分：选哪条路

| 你的场景 | 建议路径 |
|----------|----------|
| 本地脚本/分析 | Python connector |
| Web 应用/服务调用 | REST API / Snowpark |
| BI/报表 | ODBC / JDBC |
| 临时查数据 | Snowsight |

