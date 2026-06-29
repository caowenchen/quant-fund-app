from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True, comment="基金代码")
    fund_name = Column(String(100), nullable=False, comment="基金名称")
    shares = Column(Float, nullable=False, default=0, comment="持有份额")
    cost_amount = Column(Float, nullable=False, default=0, comment="投入本金")
    avg_cost = Column(Float, nullable=False, default=0, comment="持仓成本价(净值)")
    current_nav = Column(Float, default=0, comment="当前净值")
    market_value = Column(Float, default=0, comment="当前市值")
    daily_profit = Column(Float, default=0, comment="今日收益")
    total_profit = Column(Float, default=0, comment="累计收益")
    total_profit_rate = Column(Float, default=0, comment="累计收益率")
    peak_return_rate = Column(Float, default=0, comment="历史最高收益率(移动止盈用)")
    trailing_stop_active = Column(Boolean, default=False, comment="移动止盈是否激活")
    status = Column(String(20), default="holding", comment="holding|observing|stop_loss|sold_half|sold_all")
    sector_name = Column(String(50), default="", comment="关联板块名称")
    sector_code = Column(String(20), default="", comment="关联板块代码")
    sector_change_pct = Column(Float, default=0, comment="关联板块涨跌幅")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    fund_name = Column(String(100), nullable=False)
    decision = Column(String(50), nullable=False, comment="操作建议")
    reason = Column(Text, default="", comment="决策原因")
    action = Column(String(50), default="", comment="具体动作: buy/add/hold/observe/stop_loss/sell_half/sell_all")
    current_return_rate = Column(Float, default=0)
    peak_return_rate = Column(Float, default=0)
    current_nav = Column(Float, default=0)
    sector_change_pct = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.now)


class FundSectorMapping(Base):
    __tablename__ = "fund_sector_mapping"

    fund_code = Column(String(20), primary_key=True)
    fund_name = Column(String(100), default="")
    sector_name = Column(String(50), nullable=False)
    sector_code = Column(String(20), default="")
    index_code = Column(String(20), default="")


class TradingCalendar(Base):
    __tablename__ = "trading_calendar"

    date = Column(String(10), primary_key=True, comment="YYYY-MM-DD")
    is_trading_day = Column(Boolean, default=True)


class StrategyState(Base):
    __tablename__ = "strategy_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    entry_nav = Column(Float, default=0, comment="入场净值")
    entry_date = Column(String(20), default="")
    highest_nav = Column(Float, default=0, comment="持仓期间最高净值")
    highest_return_rate = Column(Float, default=0, comment="持仓期间最高收益率")
    trailing_active = Column(Boolean, default=False)
    position_status = Column(String(20), default="full", comment="full|half|empty")
    can_add_position = Column(Boolean, default=True, comment="是否允许加仓")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
