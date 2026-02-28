# Economic News Skill

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![Version](https://img.shields.io/badge/version-1.0.0-orange.svg)

为 OpenClaw 智能体提供的实时财经新闻服务，数据源自金十数据。

## 功能特性

- Top 10 重要事件（编辑精选）
- 实时快讯，支持 SSE 订阅
- 19 个新闻分类及子分类
- 关键词搜索
- 全球市场交易状态（18 个市场）

## 快速开始

### 环境要求

- Python 3.10+
- Playwright

### 安装

```bash
# 克隆仓库
git clone https://github.com/HenryXiaoYang/economic-news-skill.git
cd economic-news-skill

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 启动服务
python3 main.py
```

服务将在 `http://localhost:8765` 启动。

## 使用方法

### API 接口

| 接口 | 说明 |
|------|------|
| `GET /` | 服务状态 |
| `GET /top10` | 重要事件 Top10 |
| `GET /latest` | 最新快讯 |
| `GET /categories` | 所有分类 |
| `GET /category/{id}` | 按分类获取 |
| `GET /search?q=关键词` | 搜索快讯 |
| `GET /clock` | 市场交易状态 |
| `GET /events` | SSE 实时订阅 |
| `GET /health` | 健康检查 |

### 工作流

```
需要财经新闻？
|
+-- 重要事件 --> GET /top10
|
+-- 最新快讯
|   +-- 单次获取 --> GET /latest
|   +-- 实时监听 --> GET /events (SSE)
|
+-- 分类新闻
|   +-- 1. GET /categories（获取分类 ID）
|   +-- 2. GET /category/{id}
|
+-- 搜索关键词 --> GET /search?q=关键词
|
+-- 市场状态 --> GET /clock
```

### 实时通知

**方式一：定时汇总（通过 cron）**

```bash
openclaw cron add \
  --name "economic-news" \
  --schedule "*/10 * * * *" \
  --task "获取最新 5 条财经快讯并发送给用户"
```

**方式二：即时推送（通过 SSE）**

```bash
python3 notify.py -t "user:ou_xxx" -c feishu
python3 notify.py -t "user:ou_xxx" -c feishu --important  # 仅重要快讯
```

### 常用分类 ID

| ID | 分类 | ID | 分类 |
|----|------|----|------|
| 2 | 黄金 | 53 | 美联储 |
| 6 | 石油 | 46 | 中东风云 |
| 12 | 外汇 | 167 | 俄乌冲突 |
| 27 | 美股 | 29 | A股 |

## 配置

服务默认运行在 8765 端口，可修改 `main.py` 更改。


## AI 安装指南

供 AI 智能体安装此 skill 的分步教程：

```
1. 克隆仓库到 OpenClaw skills 目录：
   cd ~/.openclaw/skills
   git clone https://github.com/HenryXiaoYang/economic-news-skill.git
   cd economic-news-skill

2. 创建并激活虚拟环境：
   python3 -m venv .venv
   source .venv/bin/activate

3. 安装 Python 依赖：
   pip install -r requirements.txt

4. 安装 Playwright 浏览器：
   playwright install chromium

5. 后台启动服务：
   nohup python3 main.py > /tmp/economic-news.log 2>&1 &

6. 验证服务运行：
   curl http://localhost:8765/health

7. （可选）启动实时通知监听：
   source .venv/bin/activate
   pip install httpx sseclient-py
   nohup python3 notify.py -t "user:ou_xxx" -c feishu > /tmp/economic-news-notify.log 2>&1 &
```

## 许可证

[MIT](LICENSE)
