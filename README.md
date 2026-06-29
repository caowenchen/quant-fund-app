# 量化基金交易监控系统

基于规则的量化基金交易信号系统，支持持仓管理、策略评估、邮件报告和移动端查看。

## 功能特性

- **实时数据** — 东方财富基金净值、板块涨跌幅、指数行情
- **量化策略** — 亏损止损、移动止盈、加仓控制的完整交易规则
- **定时任务** — 交易日 14:30 自动评估、14:40 发送决策邮件、每日 18:00 持仓报告
- **Web 面板** — 深色主题监控面板，支持持仓管理、CSV 导入、策略评估、邮件发送
- **移动端** — React Native (Expo) 实现的移动 App，三大 Tab 页面

## 交易策略

| 规则 | 条件 | 操作 |
|------|------|------|
| 停止加仓 | 亏损 ≥ 6% | 进入观察，禁止加仓 |
| 止损 | 亏损 ≥ 7.5% | 全部卖出止损 |
| 启动移动止盈 | 盈利 ≥ 10% | 激活移动止盈跟踪 |
| 卖一半 | 从最高点回撤 ≥ 3% | 卖出一半仓位 |
| 卖完 | 从最高点回撤 ≥ 5% | 全部卖出止盈 |

## 项目结构

```
quant-fund-app/
├── backend/                  # Python Flask 后端
│   ├── main.py               # API 服务 + Web 面板
│   ├── strategy.py           # 量化策略引擎
│   ├── fund_data.py          # 基金/板块/指数数据抓取
│   ├── scheduler.py          # 定时任务调度
│   ├── models.py             # 数据库模型
│   ├── database.py           # 数据库连接
│   ├── email_sender.py       # QQ邮箱发送
│   ├── alipay_scraper.py     # 支付宝持仓抓取(实验)
│   ├── config.py             # 全局配置
│   ├── run.py                # 启动入口
│   └── requirements.txt      # Python 依赖
│
└── mobile/                   # React Native 移动端
    ├── App.js                # 应用入口
    ├── app.json              # Expo 配置
    ├── package.json          # JS 依赖
    └── src/
        ├── screens/          # 页面: 持仓、信号、设置
        └── services/         # API 调用封装
```

## 快速开始

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 配置邮箱等信息
python run.py
```

访问 `http://localhost:5000` 打开监控面板。

### 2. 移动端

```bash
cd mobile
npm install
npx expo start
```

使用 Expo Go 扫码或连接模拟器运行。

## 配置说明

复制 `.env.example` 为 `.env`，按需填写：

| 配置项 | 说明 |
|--------|------|
| `QQ_EMAIL` | QQ 邮箱地址（用于接收交易信号邮件） |
| `QQ_EMAIL_AUTH_CODE` | QQ 邮箱 SMTP 授权码 |
| `DATABASE_URL` | 数据库路径，默认 SQLite |
| `STOP_LOSS_RATE` | 止损线，默认 -0.075 (-7.5%) |
| `TRAILING_STOP_TRIGGER` | 移动止盈触发线，默认 0.10 (10%) |

策略参数可在 `config.py` 中直接修改。

## 技术栈

- **后端**: Python 3, Flask, SQLAlchemy, APScheduler, akshare
- **移动端**: React Native, Expo, React Navigation
- **数据源**: 东方财富 API (fundgz.1234567.com.cn, push2.eastmoney.com)
