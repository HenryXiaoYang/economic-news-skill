# Economic News - 金十数据快讯服务

实时获取金十数据财经快讯、重要事件、分类新闻和全球市场交易状态。

## 服务地址

```
http://localhost:8765
```

---

## 工作流

### 你需要什么类型的财经新闻？

```
需要财经新闻
├── 重要事件（编辑精选热点）
│   └── GET /top10
│
├── 实时快讯
│   ├── 单次获取 → GET /latest
│   └── 持续监听 → GET /events (SSE)
│
├── 特定分类的新闻
│   ├── 1. GET /categories → 获取分类列表，找到分类 ID
│   └── 2. GET /category/{id} → 用分类 ID 获取快讯
│
├── 搜索特定关键词
│   └── GET /search?q=关键词
│
└── 市场交易状态
    ├── 所有市场 → GET /clock
    └── 特定市场 → GET /clock/{市场名}
```

---

### 工作流详解

#### 场景 1：获取重要事件

用户问"最近有什么重要新闻"、"今天的热点是什么"

```bash
GET /top10
```

#### 场景 2：获取实时快讯

**单次获取**（用户问"最新消息"、"刚发生了什么"）

```bash
GET /latest?limit=20
```

**持续监听**（用户说"帮我盯着"、"有新消息告诉我"）

先问用户选择哪种方式：

**选项一：定时汇总（每 x 分钟）**

启动一个 cron job，定时获取最新快讯并通知：

```bash
# 创建 cron：每 10 分钟获取一次
openclaw cron add \
  --name "economic-news-notify" \
  --schedule "*/10 * * * *" \
  --task "获取 Jin10 最新 5 条快讯并发送给用户 [target]"
```

**选项二：实时通知（有消息立即推送）**

使用 notify.py 脚本监听 SSE：

```bash
# 首次运行需要安装依赖
cd ~/.openclaw/skills/economic-news-skill
python3 -m venv .venv
source .venv/bin/activate
pip install httpx sseclient-py

# 启动实时监听（后台运行）
source .venv/bin/activate  # 如已激活可跳过
nohup python3 notify.py -t "user:ou_xxx" -c feishu > /tmp/economic-news-notify.log 2>&1 &

# 仅通知重要快讯
nohup python3 notify.py -t "user:ou_xxx" -c feishu --important > /tmp/economic-news-notify.log 2>&1 &

# 停止监听
pkill -f "notify.py"
```

notify.py 参数：
| 参数 | 说明 |
|------|------|
| -t, --target | 目标用户/群组 ID（必填） |
| -c, --channel | 通知渠道：feishu/telegram/discord |
| --important | 仅通知重要快讯 |

#### 场景 3：获取特定分类新闻

用户问"黄金相关的新闻"、"中东局势"

**步骤 1**：获取分类列表
```bash
GET /categories
# 找到分类 ID，如：黄金=2, 中东风云=46
```

**步骤 2**：按分类获取
```bash
GET /category/2?limit=20
```

**常用分类 ID 速查：**
| ID | 名称 | ID | 名称 |
|----|------|----|------|
| 2 | 黄金 | 53 | 美联储 |
| 6 | 石油 | 46 | 中东风云 |
| 12 | 外汇 | 167 | 俄乌冲突 |
| 27 | 美股 | 29 | A股 |

#### 场景 4：搜索关键词

用户问"有没有关于特斯拉的消息"

```bash
GET /search?q=特斯拉&limit=10
```

#### 场景 5：查看市场交易状态

用户问"美股开盘了吗"、"现在哪些市场在交易"

```bash
# 所有市场
GET /clock

# 仅交易中
GET /clock?trading_only=true

# 特定市场（模糊匹配）
GET /clock/纳斯达克
```

---

## API 参考

### GET /

服务状态

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| service | string | 服务名称 |
| version | string | 版本号 |
| connected | boolean | 是否已连接数据源 |
| last_update | string/null | 最后更新时间 (ISO 8601) |
| top_list_count | int | 重要事件数量 |
| flash_count | int | 快讯缓存数量 |
| classify_count | int | 分类数量 |
| sse_clients | int | SSE 订阅客户端数 |

#### 示例

```json
{
  "service": "Economic News",
  "version": "4.3.0",
  "connected": true,
  "last_update": "2026-02-28T21:39:14.948241",
  "top_list_count": 10,
  "flash_count": 41,
  "classify_count": 19,
  "sse_clients": 0
}
```

---

### GET /top10

重要事件 Top10（编辑精选）

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| count | int | 返回数量 |
| updated | string/null | 最后更新时间 |
| items | array | 事件列表 |

**items 元素字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| rank | int | 排名 (1-10) |
| title | string | 事件标题 |
| content | string | 事件详情 |
| time | string | 发布时间 (YYYY-MM-DD HH:mm:ss) |

#### 示例

```json
{
  "success": true,
  "count": 10,
  "items": [
    {
      "rank": 1,
      "title": "伊朗称目前发射导弹只是清库存 即将投入一系列“从未面世的神秘武器”",
      "content": "金十数据2月28日讯，伊朗革命卫队高级指挥官贾巴里向美国总统特朗普发出了严厉警告。他公开表示，伊朗在今日反击行动中所动用的导弹仅仅是“仓库里的陈旧库存”，意在暗示伊朗真正的战略底牌尚未打出。贾巴里进一步透露，伊朗即将在战场上展示并投入一系列“从未面世的神秘武器”。他强调，这些尖端装备的威力和技术水平将远超外界想象，旨在给侵略者带来毁灭性的打击。",
      "time": "2026-02-28 21:25:37"
    },
    {
      "rank": 2,
      "title": "据伊朗媒体Fars News：油轮暂停通过霍尔木兹海峡。",
      "content": "据伊朗媒体Fars News：油轮暂停通过霍尔木兹海峡。",
      "time": "2026-02-28 21:12:15"
    }
  ],
  "updated": "2026-02-28T21:39:14.948241"
}
```

---

### GET /latest

最新快讯列表

#### 输入参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| limit | int | 50 | 返回条数，最大 200 |
| channel | int | - | 分类 ID 筛选（可选） |

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| count | int | 总缓存数量 |
| items | array | 快讯列表 |

**items 元素字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| time | string | 发布时间 (YYYY-MM-DD HH:mm:ss) |
| important | boolean | 是否重要快讯 |
| title | string | 快讯标题 |
| content | string | 快讯详情 |

#### 示例

```bash
GET /latest?limit=2
```

```json
{
  "success": true,
  "count": 41,
  "items": [
    {
      "time": "2026-02-28 21:39:06",
      "important": false,
      "title": "伊朗紧急致电沙特、阿联酋、卡塔尔、科威特、巴林、伊拉克",
      "content": "金十数据2月28日讯，据伊朗外交部消息，针对美以联军对伊朗发动的军事行动，伊朗外长阿拉格齐先后紧急致电沙特、阿联酋、卡塔尔、科威特、巴林及伊拉克6国的外长。阿拉格奇在通话中严正指出，此次军事侵略严重违反了《联合国宪章》，是公然破坏国际和平与安全的犯罪行为，并重申伊朗将动用全部军事能力行使固有的自卫权。这6个国家境内都有美军基地。阿拉格齐特别强调了地区国家的国际法责任，即严禁参与或协助针对第三国的侵略行动。他发出明确警告：所有地区国家都有义务防止美国和以色列利用其领土或领空对伊朗实施打击。伊朗武装力量已达成共识，将根据国际法准则，把所有侵略行动的发起点、来源地，以及任何试图拦截伊朗防御性反击的行为，全部视为“合法打击目标”。"
    },
    {
      "time": "2026-02-28 21:37:58",
      "important": true,
      "title": "据阿拉伯电视台：沙特局势正常，未接到爆炸事件报告。",
      "content": "据阿拉伯电视台：沙特局势正常，未接到爆炸事件报告。"
    }
  ]
}
```

---

### GET /categories

获取所有分类

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| count | int | 主分类数量 |
| items | array | 分类列表 |

**items 元素字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 分类 ID |
| name | string | 分类名称 |
| child | array | 子分类列表（可选） |

**child 元素字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 子分类 ID |
| name | string | 子分类名称 |

#### 示例

```json
{
  "success": true,
  "count": 19,
  "items": [
    {
      "id": 1,
      "name": "贵金属",
      "child": [
        {
          "id": 2,
          "name": "黄金"
        },
        {
          "id": 3,
          "name": "白银"
        },
        {
          "id": 4,
          "name": "钯金"
        },
        {
          "id": 5,
          "name": "铂金"
        }
      ]
    },
    {
      "id": 6,
      "name": "石油",
      "child": [
        {
          "id": 7,
          "name": "WTI原油"
        },
        {
          "id": 8,
          "name": "布伦特原油"
        },
        {
          "id": 9,
          "name": "欧佩克"
        },
        {
          "id": 10,
          "name": "页岩气"
        },
        {
          "id": 11,
          "name": "原油市场报告"
        }
      ]
    }
  ]
}
```

---

### GET /category/{id}

按分类获取快讯

#### 输入参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| id | int | - | 分类 ID（路径参数，必填） |
| limit | int | 50 | 返回条数，最大 200 |

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| category_id | int | 分类 ID |
| category_name | string/null | 分类名称 |
| count | int | 匹配数量 |
| items | array | 快讯列表（字段同 /latest） |

#### 示例

```bash
GET /category/2?limit=2
```

```json
{
  "success": true,
  "category_id": 2,
  "category_name": "黄金",
  "count": 0,
  "items": []
}
```

---

### GET /search

搜索快讯

#### 输入参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| q | string | - | 搜索关键词（必填） |
| limit | int | 20 | 返回条数，最大 100 |

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| keyword | string | 搜索关键词 |
| count | int | 结果数量 |
| items | array | 快讯列表（字段同 /latest） |

#### 示例

```bash
GET /search?q=伊朗&limit=2
```

```json
{
  "success": true,
  "keyword": "伊朗",
  "count": 2,
  "items": [
    {
      "time": "2026-02-28 21:40:55",
      "important": false,
      "title": "【伊朗最高领袖和总统目前状况良好】金十数据2月28日讯，从多方了解到，伊朗最高领袖哈梅内伊和伊朗总统佩泽希齐扬目前安全状况良好，身体健康。",
      "content": "【伊朗最高领袖和总统目前状况良好】金十数据2月28日讯，从多方了解到，伊朗最高领袖哈梅内伊和伊朗总统佩泽希齐扬目前安全状况良好，身体健康。"
    },
    {
      "time": "2026-02-28 21:40:22",
      "important": true,
      "title": "【伊朗媒体称至少35枚导弹“成功袭击”以色列】金十数据2月28日讯，伊朗迈赫尔通讯社2月28日报道称，至少35枚伊朗导弹“成功袭击”以色列。",
      "content": "【伊朗媒体称至少35枚导弹“成功袭击”以色列】金十数据2月28日讯，伊朗迈赫尔通讯社2月28日报道称，至少35枚伊朗导弹“成功袭击”以色列。"
    }
  ]
}
```

---

### GET /clock

全球市场交易状态

#### 输入参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| trading_only | boolean | false | 仅返回交易中的市场 |

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 请求是否成功 |
| count | int | 市场数量 |
| server_time | string | 服务器时间 (ISO 8601) |
| markets | array | 市场列表 |

**markets 元素字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 市场名称 |
| start_time | string | 开盘时间 (HH:mm) |
| end_time | string | 收盘时间 (HH:mm) |
| utc | number | UTC 时区偏移 |
| local_time | string | 市场当地时间 (HH:mm) |
| local_date | string | 市场当地日期 (YYYY-MM-DD) |
| status | string | 交易状态：交易中/已收盘/休市 |
| is_trading | boolean | 是否正在交易 |

#### 示例

```json
{
  "success": true,
  "count": 18,
  "server_time": "2026-02-28T21:45:13.804160",
  "markets": [
    {
      "name": "新西兰证券交易所",
      "start_time": "06:00",
      "end_time": "12:45",
      "utc": 12,
      "local_time": "01:45",
      "local_date": "2026-03-01",
      "status": "休市",
      "is_trading": false
    },
    {
      "name": "迪拜金融市场",
      "start_time": "14:00",
      "end_time": "17:50",
      "utc": 4,
      "local_time": "17:45",
      "local_date": "2026-02-28",
      "status": "休市",
      "is_trading": false
    },
    {
      "name": "巴西证券交易所",
      "start_time": "21:00",
      "end_time": "04:55",
      "utc": -3,
      "local_time": "10:45",
      "local_date": "2026-02-28",
      "status": "休市",
      "is_trading": false
    }
  ]
}
```

---

### GET /clock/{market_name}

查询特定市场状态（支持模糊匹配）

#### 输入参数

| 参数 | 类型 | 说明 |
|------|------|------|
| market_name | string | 市场名称关键词（路径参数） |

#### 输出字段

成功时返回单个市场信息（字段同 /clock 的 markets 元素）

#### 示例

```bash
GET /clock/上海
```

```json
{
  "success": true,
  "name": "上海证券交易所",
  "start_time": "09:30",
  "end_time": "15:00",
  "utc": 8,
  "local_time": "21:45",
  "local_date": "2026-02-28",
  "status": "休市",
  "is_trading": false
}
```

---

### GET /events

SSE 实时订阅

#### 输入参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| history | boolean | true | 是否推送历史消息。设为 false 则只推送连接后的新消息 |

#### 事件类型

| 事件 | 说明 |
|------|------|
| toplist | 重要事件更新 |
| flash | 新快讯 |
| keepalive | 心跳（每 30 秒） |

#### flash 事件字段

| 字段 | 类型 | 说明 |
|------|------|------|
| time | string | 发布时间 |
| important | boolean | 是否重要 |
| title | string | 标题 |
| content | string | 详情 |

#### 示例

```bash
curl -N http://localhost:8765/events
```

```
event: toplist
data: {"items": [...]}

event: flash
data: {"time": "2026-02-28 21:30:53", "important": true, "title": "快讯标题", "content": "快讯详情"}

: keepalive
```

---

### GET /health

健康检查

#### 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 状态："ok" |
| connected | boolean | 数据源连接状态 |

#### 示例

```json
{
  "status": "ok",
  "connected": true
}
```

---

## 安装

### 环境要求

- Python 3.10+
- Playwright

### 安装步骤

```bash
# 克隆仓库到 skills 目录
cd ~/.openclaw/skills
git clone https://github.com/HenryXiaoYang/economic-news-skill.git
cd economic-news-skill

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
playwright install chromium
```

---

## 服务管理

### 启动

```bash
cd ~/.openclaw/skills/economic-news-skill
source .venv/bin/activate
nohup python3 main.py > /tmp/economic-news.log 2>&1 &
```

### 停止

```bash
pkill -f "python.*economic-news.*main.py"
```

### 日志

```bash
tail -f /tmp/economic-news.log
```
