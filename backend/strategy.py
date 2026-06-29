from typing import Dict, List, Optional, Tuple
from config import Config


class StrategyEngine:

    def __init__(self):
        self.cfg = Config

    def evaluate(self, fund_code: str, fund_name: str,
                 current_nav: float, avg_cost: float, market_value: float,
                 shares: float, cost_amount: float,
                 peak_return_rate: float = 0,
                 trailing_active: bool = False,
                 position_status: str = "full",
                 can_add: bool = True,
                 sector_change_pct: float = 0) -> dict:
        """
        根据策略评估单只基金的操作建议

        返回:
        {
            "decision": "观望" | "止损" | "卖一半" | "卖完" | "持有" | "可加仓",
            "action": "observe" | "stop_loss" | "sell_half" | "sell_all" | "hold" | "add",
            "reason": str,
            "current_return_rate": float,
            "peak_return_rate": float,
            "trailing_active": bool,
            "alert_level": "normal" | "warning" | "danger" | "profit",
        }
        """
        if cost_amount <= 0 or market_value <= 0:
            return self._result("hold", "持有", "持仓数据不完整 (本金或市值为0)", 0, peak_return_rate, trailing_active, "normal")

        total_profit = market_value - cost_amount
        current_return_rate = (market_value - cost_amount) / cost_amount if cost_amount > 0 else 0

        new_peak = max(peak_return_rate, current_return_rate)
        new_trailing = trailing_active

        # 1. 亏损 7.5%: 止损
        if current_return_rate <= self.cfg.STOP_LOSS_RATE:
            return self._result(
                "stop_loss", "止损",
                f"亏损已达 {current_return_rate:.2%}, 触发止损线 {self.cfg.STOP_LOSS_RATE:.0%}, 建议全部卖出止损",
                current_return_rate, new_peak, new_trailing, "danger"
            )

        # 2. 亏损 6%: 停止加仓, 观察
        if current_return_rate <= self.cfg.STOP_ADD_LOSS_RATE:
            return self._result(
                "observe", "观察",
                f"亏损 {current_return_rate:.2%}, 达到观察线 {self.cfg.STOP_ADD_LOSS_RATE:.0%}, 停止加仓, 密切观察",
                current_return_rate, new_peak, new_trailing, "warning"
            )

        # 3. 盈利 10%: 启动移动止盈
        if current_return_rate >= self.cfg.TRAILING_STOP_TRIGGER and not trailing_active:
            new_trailing = True
            new_peak = current_return_rate

        # 4. 移动止盈已激活时
        if trailing_active:
            drawdown = new_peak - current_return_rate

            # 从最高收益回撤 5%: 卖完
            if drawdown >= self.cfg.TRAILING_DRAWDOWN_ALL:
                return self._result(
                    "sell_all", "卖完",
                    f"盈利从最高 {new_peak:.2%} 回撤 {drawdown:.2%}, 触发全部卖出 (回撤>{self.cfg.TRAILING_DRAWDOWN_ALL:.0%})",
                    current_return_rate, new_peak, new_trailing, "danger"
                )

            # 从最高收益回撤 3%: 卖一半
            if drawdown >= self.cfg.TRAILING_DRAWDOWN_HALF and position_status == "full":
                return self._result(
                    "sell_half", "卖一半",
                    f"盈利从最高 {new_peak:.2%} 回撤 {drawdown:.2%}, 触发卖出一半 (回撤>{self.cfg.TRAILING_DRAWDOWN_HALF:.0%})",
                    current_return_rate, new_peak, new_trailing, "warning"
                )

            # 已卖一半, 继续回撤到5%卖完
            if drawdown >= self.cfg.TRAILING_DRAWDOWN_ALL and position_status == "half":
                return self._result(
                    "sell_all", "卖完",
                    f"已减半仓, 继续回撤 {drawdown:.2%}, 触发全部卖出",
                    current_return_rate, new_peak, new_trailing, "danger"
                )

            # 还在移动止盈监控中, 但未触发卖出
            return self._result(
                "hold", "持有(移动止盈中)",
                f"移动止盈激活, 当前收益 {current_return_rate:.2%}, 最高 {new_peak:.2%}, 回撤 {drawdown:.2%}",
                current_return_rate, new_peak, new_trailing, "profit"
            )

        # 5. 盈利但未到10%: 正常持有, 可加仓
        if current_return_rate > 0:
            if can_add:
                return self._result(
                    "hold", "持有(可加仓)",
                    f"当前收益 {current_return_rate:.2%}, 板块涨跌 {sector_change_pct:+.2%}, 可考虑加仓",
                    current_return_rate, new_peak, new_trailing, "profit"
                )
            return self._result(
                "hold", "持有",
                f"当前收益 {current_return_rate:.2%}",
                current_return_rate, new_peak, new_trailing, "profit"
            )

        # 6. 亏损但未到6%: 可考虑加仓
        if can_add:
            return self._result(
                "hold", "持有(可加仓)",
                f"小幅亏损 {current_return_rate:.2%}, 板块涨跌 {sector_change_pct:+.2%}, 可考虑逢低加仓",
                current_return_rate, new_peak, new_trailing, "normal"
            )
        return self._result(
            "hold", "持有",
            f"小幅亏损 {current_return_rate:.2%}, 继续持有",
            current_return_rate, new_peak, new_trailing, "normal"
        )

    def _result(self, action: str, decision: str, reason: str,
                current_rate: float, peak_rate: float,
                trailing_active: bool, alert: str) -> dict:
        return {
            "action": action,
            "decision": decision,
            "reason": reason,
            "current_return_rate": round(current_rate, 4),
            "peak_return_rate": round(peak_rate, 4),
            "trailing_active": trailing_active,
            "alert_level": alert,
        }
