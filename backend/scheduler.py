from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import time

from database import SessionLocal
from models import Holding, Decision, StrategyState
from fund_data import FundDataService
from strategy import StrategyEngine
from email_sender import EmailSender
from alipay_scraper import AlipayScraper
from config import Config


class FundScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.email_sender = EmailSender()
        self.strategy = StrategyEngine()
        self.fund_data = FundDataService()

    def start(self):
        self.scheduler.add_job(
            self.task_daily_holdings_check,
            CronTrigger(hour=18, minute=0),
            id="daily_holdings_check",
            name="每日18:00 持仓检查",
            misfire_grace_time=300,
        )

        self.scheduler.add_job(
            self.task_trading_signal,
            CronTrigger(day_of_week="mon-fri", hour=14, minute=30),
            id="trading_signal_1430",
            name="交易日14:30 板块涨跌&交易信号",
            misfire_grace_time=300,
        )

        self.scheduler.add_job(
            self.task_send_decision,
            CronTrigger(day_of_week="mon-fri", hour=14, minute=40),
            id="send_decision_1440",
            name="交易日14:40 发送决策邮件",
            misfire_grace_time=300,
        )

        self.scheduler.start()
        print("[Scheduler] 定时任务已启动:")
        print("  - 每日 18:00  持仓检查")
        print("  - 交易日 14:30  板块分析 & 交易信号生成")
        print("  - 交易日 14:40  发送决策邮件")

    def stop(self):
        self.scheduler.shutdown()

    def task_daily_holdings_check(self):
        """每日18:00 检查持仓"""
        print(f"\n[Scheduler] ===== {datetime.now()} 每日持仓检查 =====")
        try:
            self._update_holdings_from_alipay()
            self._update_fund_nav()
            self._send_holdings_report()
        except Exception as e:
            print(f"[Scheduler] 持仓检查异常: {e}")

    def task_trading_signal(self):
        """交易日14:30 板块分析和交易信号"""
        if not FundDataService.is_trading_day():
            print(f"[Scheduler] {datetime.now()} 非交易日, 跳过交易信号")
            return

        print(f"\n[Scheduler] ===== {datetime.now()} 板块分析 & 交易信号 =====")
        try:
            self._update_sector_data()
            self._update_fund_nav()
            self._evaluate_strategy()
        except Exception as e:
            print(f"[Scheduler] 交易信号异常: {e}")

    def task_send_decision(self):
        """交易日14:40 发送决策邮件"""
        if not FundDataService.is_trading_day():
            print(f"[Scheduler] {datetime.now()} 非交易日, 跳过发送邮件")
            return

        print(f"\n[Scheduler] ===== {datetime.now()} 发送决策邮件 =====")
        try:
            self._send_decision_email()
        except Exception as e:
            print(f"[Scheduler] 发送邮件异常: {e}")

    def _update_holdings_from_alipay(self):
        """更新持仓子步 — 根据配置决定数据来源"""
        if Config.AUTO_ALIPAY_SCRAPE:
            self._scrape_alipay_and_merge()
        else:
            self._check_existing_holdings()

    def _scrape_alipay_and_merge(self):
        """支付宝自动抓取 → 候选确认 → 合并到 holdings"""
        print("[Scheduler] 支付宝自动抓取...")
        try:
            scraper = AlipayScraper()
            holdings = scraper.fetch_holdings()
        except Exception as e:
            print(f"[Scheduler] 支付宝抓取异常: {e}")
            holdings = []

        if not holdings or len(holdings) < 6:
            print("[Scheduler] 自动抓取不完整, 使用已有数据库持仓")
            self._check_existing_holdings()
            return

        missing = [h for h in holdings
                   if h.get("profit_amount") is None or h.get("profit_rate") is None]
        if missing:
            print(f"[Scheduler] {len(missing)} 只收益缺失, 不自动覆盖, 使用已有持仓")
            self._check_existing_holdings()
            return

        print(f"[Scheduler] 候选持仓 {len(holdings)} 只, 等待确认...")
        if Config.AUTO_IMPORT_CONFIRM:
            try:
                confirm = input("[Scheduler] 输入 y 写入数据库: ").strip().lower()
                if confirm != "y":
                    print("[Scheduler] 用户取消, 使用已有持仓")
                    self._check_existing_holdings()
                    return
            except (EOFError, KeyboardInterrupt):
                print("[Scheduler] 非交互模式, 跳过写入, 使用已有持仓")
                self._check_existing_holdings()
                return

        self._merge_holdings_to_db(holdings)

    def _check_existing_holdings(self):
        """检查数据库已有持仓"""
        db = SessionLocal()
        try:
            count = db.query(Holding).count()
            if count == 0:
                print("[Scheduler] 当前无持仓数据。请通过网页手动添加或 CSV 导入。")
            else:
                print(f"[Scheduler] 使用数据库已有 {count} 条持仓")
        finally:
            db.close()

    def _merge_holdings_to_db(self, holdings):
        db = SessionLocal()
        try:
            for h in holdings:
                fund_code = h.get("fund_code", "")
                fund_name = h.get("fund_name", "")

                if not fund_code and fund_name:
                    fund_code = f"__{fund_name}"

                existing = None
                if fund_code:
                    existing = db.query(Holding).filter(Holding.fund_code == fund_code).first()
                if not existing and fund_name:
                    existing = db.query(Holding).filter(Holding.fund_name == fund_name).first()

                if existing:
                    if fund_code and not fund_code.startswith("__"):
                        existing.fund_code = fund_code
                    existing.fund_name = fund_name
                    existing.shares = h.get("shares", existing.shares)
                    existing.cost_amount = h.get("cost_amount", existing.cost_amount)
                    existing.avg_cost = h.get("avg_cost", existing.avg_cost)
                    existing.market_value = h.get("market_value", existing.market_value)
                    existing.total_profit = h.get("total_profit", existing.total_profit)
                    existing.total_profit_rate = h.get("total_profit_rate", existing.total_profit_rate)
                else:
                    sector_info = Config.FUND_SECTOR_MAP.get(h.get("fund_code", ""), {})
                    new_holding = Holding(
                        fund_code=fund_code,
                        fund_name=fund_name,
                        shares=h.get("shares", 0),
                        cost_amount=h.get("cost_amount", 0),
                        avg_cost=h.get("avg_cost", 0),
                        market_value=h.get("market_value", 0),
                        total_profit=h.get("total_profit", 0),
                        total_profit_rate=h.get("total_profit_rate", 0),
                        sector_name=sector_info.get("name", ""),
                        sector_code=sector_info.get("sector_code", ""),
                    )
                    db.add(new_holding)

                st = None
                if fund_code:
                    st = db.query(StrategyState).filter(StrategyState.fund_code == fund_code).first()
                if not st:
                    st = StrategyState(
                        fund_code=fund_code,
                        entry_nav=h.get("avg_cost", 0),
                        entry_date=datetime.now().strftime("%Y-%m-%d"),
                        highest_return_rate=h.get("total_profit_rate", 0),
                        trailing_active=False,
                        position_status="full",
                        can_add_position=True,
                    )
                    db.add(st)

            db.commit()
            print(f"[Scheduler] 已更新 {len(holdings)} 条持仓记录")
        except Exception as e:
            db.rollback()
            print(f"[Scheduler] 数据库更新失败: {e}")
        finally:
            db.close()

    def _update_fund_nav(self):
        """更新基金实时净值"""
        db = SessionLocal()
        try:
            holdings = db.query(Holding).all()
            if not holdings:
                print("[Scheduler] 无持仓数据, 跳过净值更新")
                return

            codes = [h.fund_code for h in holdings if h.fund_code and h.fund_code.isdigit() and len(h.fund_code) == 6]
            print(f"[Scheduler] 更新 {len(codes)} 只基金净值...")
            nav_data = FundDataService.get_fund_realtime_batch(codes)

            for h in holdings:
                nd = nav_data.get(h.fund_code)
                if nd:
                    h.current_nav = nd.get("estimated_nav", nd.get("nav", 0))
                    h.daily_profit = float(nd.get("estimated_change_pct", 0)) / 100 * h.shares * h.current_nav

                    if h.current_nav > 0 and h.shares > 0:
                        h.market_value = h.shares * h.current_nav
                        h.total_profit = h.market_value - h.cost_amount
                        h.total_profit_rate = h.total_profit / h.cost_amount if h.cost_amount > 0 else 0

            db.commit()
            print(f"[Scheduler] 净值更新完成")
        except Exception as e:
            db.rollback()
            print(f"[Scheduler] 净值更新失败: {e}")
        finally:
            db.close()

    def _update_sector_data(self):
        """更新关联板块的涨跌幅"""
        db = SessionLocal()
        try:
            holdings = db.query(Holding).all()
            if not holdings:
                return

            sector_codes = list(set(h.sector_code for h in holdings if h.sector_code))
            print(f"[Scheduler] 更新 {len(sector_codes)} 个板块数据...")
            sector_data = FundDataService.get_sector_realtime_batch(sector_codes)

            for h in holdings:
                if h.sector_code and h.sector_code in sector_data:
                    h.sector_change_pct = sector_data[h.sector_code].get("change_pct", 0)
                else:
                    h.sector_change_pct = 0

            db.commit()
            print(f"[Scheduler] 板块数据更新完成")
        except Exception as e:
            db.rollback()
            print(f"[Scheduler] 板块数据更新失败: {e}")
        finally:
            db.close()

    def _evaluate_strategy(self):
        """执行策略评估, 生成交易决策"""
        db = SessionLocal()
        try:
            holdings = db.query(Holding).all()
            if not holdings:
                print("[Scheduler] 无持仓, 跳过策略评估")
                return

            for h in holdings:
                st = db.query(StrategyState).filter(StrategyState.fund_code == h.fund_code).first()
                if not st:
                    st = StrategyState(
                        fund_code=h.fund_code,
                        entry_nav=h.cost_amount,
                        highest_return_rate=h.total_profit_rate or 0,
                        position_status="holding",
                    )
                    db.add(st)
                    db.flush()

                # 更新最高收益率
                if h.total_profit_rate > st.highest_return_rate:
                    st.highest_return_rate = h.total_profit_rate

                # 检查是否触发移动止盈
                if not st.trailing_active and h.total_profit_rate >= Config.TRAILING_STOP_TRIGGER:
                    st.trailing_active = True
                    st.highest_return_rate = h.total_profit_rate

                # 策略评估
                result = self.strategy.evaluate(
                    fund_code=h.fund_code,
                    fund_name=h.fund_name,
                    current_nav=h.current_nav,
                    avg_cost=h.avg_cost,
                    market_value=h.market_value,
                    shares=h.shares,
                    cost_amount=h.cost_amount,
                    peak_return_rate=st.highest_return_rate,
                    trailing_active=st.trailing_active,
                    position_status=st.position_status,
                    can_add=st.can_add_position,
                    sector_change_pct=h.sector_change_pct,
                )

                # 更新持仓状态
                h.status = result["decision"]
                h.peak_return_rate = st.highest_return_rate
                h.trailing_stop_active = st.trailing_active

                # 更新策略状态
                if result["action"] == "stop_loss":
                    st.can_add_position = False
                    st.position_status = "empty"
                elif result["action"] == "sell_all":
                    st.position_status = "empty"
                elif result["action"] == "sell_half":
                    st.position_status = "half"
                elif result["action"] == "observe":
                    st.can_add_position = False
                elif result["action"] == "hold":
                    st.can_add_position = True

                # 保存决策
                decision = Decision(
                    fund_code=h.fund_code,
                    fund_name=h.fund_name,
                    decision=result["decision"],
                    reason=result["reason"],
                    action=result["action"],
                    current_return_rate=result["current_return_rate"],
                    peak_return_rate=result["peak_return_rate"],
                    current_nav=h.current_nav,
                    sector_change_pct=h.sector_change_pct,
                )
                db.add(decision)

            db.commit()
            print(f"[Scheduler] 策略评估完成, 已为 {len(holdings)} 只基金生成决策")
        except Exception as e:
            db.rollback()
            print(f"[Scheduler] 策略评估失败: {e}")
        finally:
            db.close()

    def _send_holdings_report(self):
        """发送每日持仓报告"""
        db = SessionLocal()
        try:
            holdings = db.query(Holding).all()
            if not holdings:
                return

            holdings_data = []
            for h in holdings:
                holdings_data.append({
                    "fund_code": h.fund_code,
                    "fund_name": h.fund_name,
                    "market_value": h.market_value,
                    "total_profit": h.total_profit,
                    "total_profit_rate": h.total_profit_rate,
                    "current_nav": h.current_nav,
                    "sector_name": h.sector_name,
                    "sector_change_pct": h.sector_change_pct,
                })

            self.email_sender.send_holdings_report(Config.QQ_EMAIL, holdings_data)
        finally:
            db.close()

    def _send_decision_email(self):
        """发送交易决策邮件"""
        db = SessionLocal()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            decisions = db.query(Decision).filter(
                Decision.created_at >= f"{today} 00:00:00"
            ).order_by(Decision.created_at.desc()).all()

            if not decisions:
                print("[Scheduler] 今日无决策记录")
                return

            decisions_data = []
            alert_summary = {"danger": 0, "warning": 0, "profit": 0, "normal": 0}

            for d in decisions:
                result = self.strategy.evaluate(
                    fund_code=d.fund_code,
                    fund_name=d.fund_name,
                    current_nav=d.current_nav,
                    avg_cost=0,
                    market_value=0,
                    shares=0,
                    cost_amount=0,
                    peak_return_rate=d.peak_return_rate,
                    sector_change_pct=d.sector_change_pct,
                )
                alert = result.get("alert_level", "normal")
                alert_summary[alert] = alert_summary.get(alert, 0) + 1

                decisions_data.append({
                    "fund_code": d.fund_code,
                    "fund_name": d.fund_name,
                    "decision": d.decision,
                    "reason": d.reason,
                    "action": d.action,
                    "current_return_rate": d.current_return_rate,
                    "peak_return_rate": d.peak_return_rate,
                    "alert_level": alert,
                })

            summary_lines = []
            if alert_summary["danger"] > 0:
                summary_lines.append(f"🔴 危险信号: {alert_summary['danger']} 只基金")
            if alert_summary["warning"] > 0:
                summary_lines.append(f"🟡 警告信号: {alert_summary['warning']} 只基金")
            if alert_summary["profit"] > 0:
                summary_lines.append(f"🟢 盈利持仓: {alert_summary['profit']} 只基金")
            if alert_summary["normal"] > 0:
                summary_lines.append(f"⚪ 正常持仓: {alert_summary['normal']} 只基金")

            summary = " | ".join(summary_lines) if summary_lines else "今日无异常信号"
            self.email_sender.send_decision_report(Config.QQ_EMAIL, decisions_data, summary)
        finally:
            db.close()
