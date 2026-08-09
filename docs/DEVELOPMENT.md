# Development Guide

## 环境

项目支持 Python 3.9+；CI 与容器使用 Python 3.12。开发依赖通过项目内 `.venv` 安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

配置读取顺序为环境变量、`.env`、默认值，前缀统一为 `KYC_`。复制 `.env.example` 为 `.env`
后可覆盖数据库、数据目录、输出目录和离线模式。不要提交 `.env` 或真实客户数据。

## 常用命令

```powershell
# 可编辑安装
.\.venv\Scripts\python.exe -m pip install -e ".[dev,notebook]"

# 格式化和检查
.\.venv\Scripts\python.exe -m ruff format .
.\.venv\Scripts\python.exe -m ruff check .

# 测试
.\.venv\Scripts\python.exe -m pytest

# 数据库迁移
.\.venv\Scripts\alembic.exe upgrade head
```

## 变更规则

- 新风险因子必须更新风险策略版本，并增加解释与边界测试。
- 新外部数据源必须保存版本/hash，并提供离线 fixture 和解析契约测试。
- 名称匹配变更必须在标注 golden dataset 上同时报告 precision、recall 和警报量。
- 数据库变更必须添加 migration；不得只修改 ORM。
- 流水线失败必须显式失败，禁止把网络或解析异常转换成“无命中”。
