import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    QQ_EMAIL = os.getenv("QQ_EMAIL", "")
    QQ_EMAIL_AUTH_CODE = os.getenv("QQ_EMAIL_AUTH_CODE", "")

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///quant_fund.db")

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    APPIUM_SERVER_URL = os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")

    # 雷电模拟器配置
    LDPLAYER_ADB_PORT = int(os.getenv("LDPLAYER_ADB_PORT", 5555))
    LDPLAYER_PATH = os.getenv("LDPLAYER_PATH", "")
    LDPLAYER_INSTANCE = int(os.getenv("LDPLAYER_INSTANCE", 0))

    # 安全开关: 自动导入前是否需要确认
    AUTO_IMPORT_CONFIRM = os.getenv("AUTO_IMPORT_CONFIRM", "true").lower() == "true"

    # 支付宝自动抓取 (默认关闭, 实验功能)
    AUTO_ALIPAY_SCRAPE = os.getenv("AUTO_ALIPAY_SCRAPE", "false").lower() == "true"

    # 持仓数据源: manual / csv / alipay_candidate
    HOLDING_SOURCE = os.getenv("HOLDING_SOURCE", "manual")

    # 手动管理开关
    ENABLE_MANUAL_IMPORT = os.getenv("ENABLE_MANUAL_IMPORT", "true").lower() == "true"
    ENABLE_CSV_IMPORT = os.getenv("ENABLE_CSV_IMPORT", "true").lower() == "true"

    # 交易策略参数
    STOP_ADD_LOSS_RATE = -0.06      # 亏损6%: 停止加仓
    STOP_LOSS_RATE = -0.075         # 亏损7.5%: 止损
    TRAILING_STOP_TRIGGER = 0.10    # 盈利10%: 启动移动止盈
    TRAILING_DRAWDOWN_HALF = 0.03   # 从最高回撤3%: 卖一半
    TRAILING_DRAWDOWN_ALL = 0.05    # 从最高回撤5%: 卖完

    # 基金-板块映射 (fund_code -> sector info)
    FUND_SECTOR_MAP = {
        # 新能源类
        "001156": {"name": "新能源", "sector_code": "BK0493", "index_code": "399808"},
        "012127": {"name": "新能源车", "sector_code": "BK0900", "index_code": "399976"},
        # 半导体/芯片
        "320007": {"name": "半导体", "sector_code": "BK0489", "index_code": "990001"},
        "008281": {"name": "芯片", "sector_code": "BK0489", "index_code": "990001"},
        # 医药
        "003095": {"name": "医药", "sector_code": "BK0465", "index_code": "399989"},
        "006002": {"name": "医疗器械", "sector_code": "BK0544", "index_code": "399989"},
        # 消费/白酒
        "161725": {"name": "白酒", "sector_code": "BK0477", "index_code": "399997"},
        "005621": {"name": "消费", "sector_code": "BK0477", "index_code": "399932"},
        # 军工
        "005609": {"name": "军工", "sector_code": "BK0491", "index_code": "399967"},
        # 银行
        "001594": {"name": "银行", "sector_code": "BK0475", "index_code": "399986"},
        # 券商
        "004069": {"name": "券商", "sector_code": "BK0473", "index_code": "399975"},
        # 沪深300
        "110020": {"name": "沪深300", "sector_code": "", "index_code": "000300"},
        "510300": {"name": "沪深300", "sector_code": "", "index_code": "000300"},
        # 中证500
        "161017": {"name": "中证500", "sector_code": "", "index_code": "000905"},
        # 创业板
        "001592": {"name": "创业板", "sector_code": "", "index_code": "399006"},
        # 科创板
        "588000": {"name": "科创50", "sector_code": "", "index_code": "000688"},
    }

    # OCR 模糊匹配用的已知基金白名单 (逗号分隔, 在 .env 中配置 KNOWN_FUNDS)
    _known_funds_env = os.getenv("KNOWN_FUNDS", "")
    KNOWN_FUNDS = [f.strip() for f in _known_funds_env.split(",") if f.strip()] if _known_funds_env else [
        "易方达沪深300ETF联接A",
        "招商中证白酒指数(LOF)A",
        "天弘中证500指数增强A",
    ]

    # A股交易日历 (2025-2026 近似, 可动态更新)
    TRADING_HOURS = {
        "morning_open": "09:30",
        "morning_close": "11:30",
        "afternoon_open": "13:00",
        "afternoon_close": "15:00",
    }
