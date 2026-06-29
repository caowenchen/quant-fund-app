import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import List
from config import Config


class EmailSender:

    def __init__(self):
        self.sender_email = Config.QQ_EMAIL
        self.auth_code = Config.QQ_EMAIL_AUTH_CODE
        self.smtp_server = "smtp.qq.com"
        self.smtp_port = 587

    def send_decision_report(self, recipient: str, decisions: List[dict],
                             holdings_summary: str = "") -> bool:
        """发送交易决策报告邮件"""
        if not self.sender_email or not self.auth_code:
            print("[EmailSender] QQ邮箱未配置, 跳过发送")
            return False

        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = f"【量化交易】{today} 基金操作建议"

        body = self._build_report_html(decisions, holdings_summary)

        return self._send_email(recipient, subject, body, is_html=True)

    def send_holdings_report(self, recipient: str, holdings: List[dict]) -> bool:
        """发送每日持仓报告"""
        if not self.sender_email or not self.auth_code:
            print("[EmailSender] QQ邮箱未配置, 跳过发送")
            return False

        today = datetime.now().strftime("%Y-%m-%d")
        subject = f"【量化交易】{today} 持仓报告"

        body = self._build_holdings_html(holdings)

        return self._send_email(recipient, subject, body, is_html=True)

    def _build_report_html(self, decisions: List[dict], summary: str) -> str:
        alert_icons = {
            "danger": "🔴",
            "warning": "🟡",
            "profit": "🟢",
            "normal": "⚪",
        }

        rows = ""
        for d in decisions:
            icon = alert_icons.get(d.get("alert_level", "normal"), "⚪")
            rows += f"""
            <tr>
                <td>{icon}</td>
                <td>{d.get('fund_name', '')} ({d.get('fund_code', '')})</td>
                <td style="color:{'red' if d.get('current_return_rate', 0) < 0 else 'green'}">
                    {d.get('current_return_rate', 0):.2%}
                </td>
                <td><b>{d.get('decision', '')}</b></td>
                <td>{d.get('reason', '')}</td>
            </tr>
            """

        html = f"""
        <html>
        <head><meta charset="utf-8"><style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
            th {{ background-color: #1a1a2e; color: white; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .summary {{ background: #f0f0f0; padding: 12px; border-radius: 6px; margin: 10px 0; }}
            .footer {{ color: #999; font-size: 12px; margin-top: 20px; }}
        </style></head>
        <body>
            <h2>📊 量化交易决策报告</h2>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <div class="summary">{summary}</div>
            <table>
                <tr>
                    <th>级别</th><th>基金</th><th>收益率</th><th>操作建议</th><th>原因</th>
                </tr>
                {rows}
            </table>
            <div class="footer">
                <p>⚠ 本报告由量化交易系统自动生成, 仅供参考, 不构成投资建议。</p>
                <p>策略参数: 亏损6%观察 | 亏损7.5%止损 | 盈利10%启动移动止盈 | 回撤3%卖一半 | 回撤5%卖完</p>
            </div>
        </body>
        </html>
        """
        return html

    def send_full_report(self, recipient: str,
                         holdings: List[dict],
                         decisions: List[dict]) -> bool:
        """发送完整每日基金决策报告"""
        if not self.sender_email or not self.auth_code:
            print("[EmailSender] QQ邮箱未配置, 跳过发送")
            return False

        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = f"【量化交易】{today} 每日基金决策报告"

        body = self._build_full_report_html(holdings, decisions)

        return self._send_email(recipient, subject, body, is_html=True)

    def _build_full_report_html(self, holdings: List[dict],
                                decisions: List[dict]) -> str:
        total_market_value = sum(h.get("market_value", 0) or 0 for h in holdings)
        total_cost = sum(h.get("cost_amount", 0) or 0 for h in holdings)
        total_profit = total_market_value - total_cost
        total_rate = total_profit / total_cost if total_cost > 0 else 0

        summary_cards = f"""
        <div style="display:flex;gap:16px;flex-wrap:wrap;margin:12px 0;">
            <div style="flex:1;min-width:130px;background:#1a1a2e;border-radius:8px;padding:14px;text-align:center;">
                <div style="color:#8b949e;font-size:12px;">持仓数量</div>
                <div style="color:#fff;font-size:22px;font-weight:bold;">{len(holdings)}</div>
            </div>
            <div style="flex:1;min-width:130px;background:#1a1a2e;border-radius:8px;padding:14px;text-align:center;">
                <div style="color:#8b949e;font-size:12px;">总市值</div>
                <div style="color:#58a6ff;font-size:22px;font-weight:bold;">{total_market_value:,.2f}</div>
            </div>
            <div style="flex:1;min-width:130px;background:#1a1a2e;border-radius:8px;padding:14px;text-align:center;">
                <div style="color:#8b949e;font-size:12px;">投入本金</div>
                <div style="color:#c9d1db;font-size:22px;font-weight:bold;">{total_cost:,.2f}</div>
            </div>
            <div style="flex:1;min-width:130px;background:#1a1a2e;border-radius:8px;padding:14px;text-align:center;">
                <div style="color:#8b949e;font-size:12px;">总盈亏</div>
                <div style="color:{'#3fb950' if total_profit>=0 else '#f85149'};font-size:22px;font-weight:bold;">{total_profit:+,.2f}</div>
            </div>
            <div style="flex:1;min-width:130px;background:#1a1a2e;border-radius:8px;padding:14px;text-align:center;">
                <div style="color:#8b949e;font-size:12px;">总收益率</div>
                <div style="color:{'#3fb950' if total_profit>=0 else '#f85149'};font-size:22px;font-weight:bold;">{total_rate:+.2%}</div>
            </div>
        </div>
        """

        holding_rows = ""
        for h in holdings:
            profit = h.get("total_profit", 0) or 0
            rate = h.get("total_profit_rate", 0) or 0
            cost = h.get("cost_amount", 0) or 0
            mkv = h.get("market_value", 0) or 0
            p_color = "#f85149" if profit < 0 else "#3fb950"
            code = h.get("fund_code", "")
            if not code or code.startswith("__"):
                code = ""
            holding_rows += f"""
            <tr>
                <td>{h.get('fund_name', '')} ({code})</td>
                <td>{mkv:,.2f}</td>
                <td>{cost:,.2f}</td>
                <td style="color:{p_color}">{profit:+,.2f}</td>
                <td style="color:{p_color}">{rate:+.2%}</td>
                <td>{h.get('sector_name', '')}</td>
            </tr>
            """

        decision_rows = ""
        for d in decisions:
            rate = d.get("current_return_rate", 0) or 0
            d_color = "#f85149" if rate < 0 else "#3fb950"
            decision_rows += f"""
            <tr>
                <td>{d.get('fund_name', '')}</td>
                <td style="color:{d_color}">{rate:+.2%}</td>
                <td><b>{d.get('decision', '')}</b></td>
                <td>{d.get('reason', '')}</td>
            </tr>
            """

        return f"""
        <html>
        <head><meta charset="utf-8"><style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; background:#0d1117; color:#c9d1db; padding:16px; }}
            h2 {{ color:#58a6ff; border-bottom:1px solid #30363d; padding-bottom:8px; }}
            h3 {{ color:#79c0ff; margin-top:24px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
            th, td {{ border: 1px solid #30363d; padding: 8px 12px; text-align: left; }}
            th {{ background-color: #161b22; color: #c9d1db; }}
            tr:nth-child(even) {{ background-color: #161b22; }}
            .rules {{ background:#161b22; border-radius:8px; padding:14px; margin:14px 0; }}
            .rules li {{ margin:6px 0; }}
            .footer {{ color: #484f58; font-size: 12px; margin-top: 20px; border-top:1px solid #30363d; padding-top:12px; }}
        </style></head>
        <body>
            <h2>📊 量化交易 — 每日基金决策报告</h2>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

            <h3>📋 一、持仓总览</h3>
            {summary_cards}

            <h3>📈 二、持仓明细</h3>
            <table>
                <tr>
                    <th>基金名称</th><th>市值</th><th>本金</th><th>累计盈亏</th><th>收益率</th><th>板块</th>
                </tr>
                {holding_rows}
            </table>

            <h3>📊 三、策略建议</h3>
            <table>
                <tr>
                    <th>基金名称</th><th>收益率</th><th>操作建议</th><th>原因</th>
                </tr>
                {decision_rows}
            </table>

            <h3>⚠ 四、风控规则</h3>
            <div class="rules">
                <li>🔴 亏损 ≤ -7.5%：<b>止损卖出</b></li>
                <li>🟡 亏损 ≤ -6%：<b>停止加仓，观察</b></li>
                <li>🟢 盈利 ≥ +10%：<b>启动移动止盈</b></li>
                <li>⚪ 其他：<b>持有</b></li>
            </div>

            <div class="footer">
                <p>⚠ 本报告由量化交易系统自动生成，仅供参考，不构成投资建议。</p>
            </div>
        </body>
        </html>
        """
        rows = ""
        total_profit = 0
        for h in holdings:
            profit = h.get("total_profit", 0)
            total_profit += profit
            rate = h.get("total_profit_rate", 0)
            color = "red" if profit < 0 else "green"
            rows += f"""
            <tr>
                <td>{h.get('fund_name', '')} ({h.get('fund_code', '')})</td>
                <td>{h.get('market_value', 0):.2f}</td>
                <td style="color:{color}">{profit:+.2f}</td>
                <td style="color:{color}">{rate:+.2%}</td>
                <td>{h.get('current_nav', 0):.4f}</td>
                <td>{h.get('sector_name', '')} {h.get('sector_change_pct', 0):+.2f}%</td>
            </tr>
            """
        total_color = "red" if total_profit < 0 else "green"

        return f"""
        <html>
        <head><meta charset="utf-8"><style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
            th {{ background-color: #1a1a2e; color: white; }}
            .total {{ font-weight: bold; font-size: 16px; }}
        </style></head>
        <body>
            <h2>📋 基金持仓报告</h2>
            <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <table>
                <tr><th>基金</th><th>市值</th><th>累计收益</th><th>收益率</th><th>净值</th><th>关联板块</th></tr>
                {rows}
            </table>
            <p class="total" style="color:{total_color}">💰 总收益: {total_profit:+.2f}</p>
        </body>
        </html>
        """

    def _send_email(self, recipient: str, subject: str, body: str, is_html: bool = True) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.sender_email
            msg["To"] = recipient
            msg["Subject"] = Header(subject, "utf-8")

            subtype = "html" if is_html else "plain"
            msg.attach(MIMEText(body, subtype, "utf-8"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.sender_email, self.auth_code)
                server.sendmail(self.sender_email, recipient, msg.as_string())

            print(f"[EmailSender] 邮件已发送至 {recipient}")
            return True
        except Exception as e:
            print(f"[EmailSender] 邮件发送失败: {e}")
            return False
