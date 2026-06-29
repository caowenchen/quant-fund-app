from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from database import init_db, SessionLocal
from models import Holding, Decision, StrategyState
from fund_data import FundDataService
from strategy import StrategyEngine
from config import Config
import csv
import io

app = Flask(__name__)
CORS(app)

strategy_engine = StrategyEngine()
fund_data_svc = FundDataService()


@app.route("/", methods=["GET"])
def index():
    db = SessionLocal()
    try:
        holdings = db.query(Holding).order_by(Holding.id).all()

        # 每只基金只取最新一条信号
        subq = db.query(
            Decision.fund_name,
            func.max(Decision.id).label("max_id")
        ).group_by(Decision.fund_name).subquery()
        decisions = db.query(Decision).join(
            subq, and_(Decision.id == subq.c.max_id)
        ).order_by(Decision.created_at.desc()).all()

        total_market_value = sum(h.market_value or 0 for h in holdings)
        total_cost = sum(h.cost_amount or 0 for h in holdings)
        total_profit = total_market_value - total_cost
        total_rate = total_profit / total_cost if total_cost > 0 else 0

        is_td = FundDataService.is_trading_day()
        is_open = FundDataService.is_market_open()

        source_tag = f'<span style="color:#d29922;">当前数据源：{Config.HOLDING_SOURCE}</span>'
        alipay_note = '<div style="color:#8b949e;font-size:12px;">支付宝自动抓取已暂停，当前使用手动持仓数据。</div>'

        holding_rows = ""
        for h in holdings:
            profit = h.total_profit or 0
            rate = h.total_profit_rate or 0
            p_color = "#f85149" if profit < 0 else "#3fb950"
            raw_status = h.status or "holding"
            status_display = {
                "持有": "持有", "观察": "观察", "holding": "持有",
                "已卖出": "已卖出", "observing": "观察",
                "stop_loss": "已卖出", "sold_half": "已卖出", "sold_all": "已卖出",
            }.get(raw_status, raw_status)
            status_color = {
                "持有": "#3fb950", "观察": "#d29922", "已卖出": "#8b949e",
            }.get(status_display, "#8b949e")
            sector_display = h.sector_name or "&mdash;"
            code_display = h.fund_code if h.fund_code and not h.fund_code.startswith("__") else "&mdash;"
            holding_rows += f"""
            <tr>
                <td>{h.fund_name or '--'}<br><small>{code_display}</small></td>
                <td>{h.market_value:,.2f}</td>
                <td>{h.cost_amount:,.2f}</td>
                <td style="color:{p_color}">{profit:+,.2f}</td>
                <td style="color:{p_color}">{rate:+.2%}</td>
                <td>{sector_display}</td>
                <td><span class="badge" style="border-color:{status_color};color:{status_color}">{status_display}</span></td>
                <td><span class="badge" style="border-color:{status_color};color:{status_color}">{status_display}</span></td>
                <td>
                    <button class="btn-sm" onclick='editHolding({h.id},"{h.fund_name}","{h.fund_code or ""}","{h.market_value}","{h.cost_amount}","{h.sector_name or ""}")'>编辑</button>
                    <button class="btn-sm btn-danger" onclick="deleteHolding({h.id})">删除</button>
                </td>
            </tr>"""

        decision_rows = ""
        for d in decisions:
            rate = d.current_return_rate or 0
            d_color = "#f85149" if rate < 0 else "#3fb950"
            alert = {"stop_loss": '🔴', "sell_all": '🔴', "sell_half": '🟡', "observe": '🟡', "hold": '🟢', "add": '🟢'}.get(d.action, '⚪')
            decision_rows += f"""
            <tr>
                <td>{alert}</td>
                <td>{d.fund_name}<br><small>{d.fund_code}</small></td>
                <td style="color:{d_color}">{rate:+.2%}</td>
                <td><b>{d.decision}</b></td>
                <td>{d.reason}</td>
                <td>{d.created_at.strftime('%m-%d %H:%M') if d.created_at else ''}</td>
            </tr>"""

        html = HTML_TEMPLATE.format(
            now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            holdings_count=len(holdings),
            total_market_value=total_market_value,
            total_cost=total_cost,
            total_profit=total_profit,
            total_rate=total_rate,
            profit_color="#f85149" if total_profit < 0 else "#3fb950",
            is_trading_day="是" if is_td else "否",
            market_status="交易中" if is_open else ("已收盘" if is_td else "休市"),
            holding_rows=holding_rows,
            decision_rows=decision_rows,
            stop_add=Config.STOP_ADD_LOSS_RATE * 100,
            stop_loss=Config.STOP_LOSS_RATE * 100,
            trigger=Config.TRAILING_STOP_TRIGGER * 100,
            half=Config.TRAILING_DRAWDOWN_HALF * 100,
            all_pct=Config.TRAILING_DRAWDOWN_ALL * 100,
            decisions_count=len(decisions),
            source_tag=source_tag,
            alipay_note=alipay_note,
        )
        return render_template_string(html)
    finally:
        db.close()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>量化交易监控</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif; background: #0d1117; color: #e6edf3; }}
.header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }}
.header h1 {{ font-size: 20px; color: #58a6ff; }}
.header .info {{ font-size: 13px; color: #8b949e; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; padding: 16px 24px; }}
.summary-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
.summary-card .label {{ font-size: 12px; color: #8b949e; }}
.summary-card .value {{ font-size: 22px; font-weight: bold; margin-top: 4px; }}
.strategy {{ display: flex; gap: 8px; flex-wrap: wrap; padding: 0 24px 16px; }}
.strategy-tag {{ background: #1a1a2e; border: 1px solid #30363d; border-radius: 6px; padding: 4px 10px; font-size: 12px; color: #c9d1d9; }}
.strategy-tag span {{ font-weight: bold; color: #e6edf3; }}
.section {{ margin: 0 24px 20px; }}
.section-title {{ font-size: 15px; font-weight: bold; color: #58a6ff; margin-bottom: 10px; border-bottom: 1px solid #21262d; padding-bottom: 6px; }}
.toolbar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }}
.btn {{ background: #21262d; border: 1px solid #30363d; color: #e6edf3; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; }}
.btn:hover {{ background: #30363d; }}
.btn-primary {{ background: #1a5d1a; border-color: #3fb950; }}
.btn-danger {{ background: #5d1a1a; border-color: #f85149; }}
.btn-sm {{ font-size: 11px; padding: 2px 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ background: #161b22; color: #8b949e; font-weight: 600; padding: 10px 12px; text-align: left; border-bottom: 1px solid #30363d; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #21262d; }}
tr:hover {{ background: #1c2128; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; border: 1px solid; font-size: 11px; font-weight: 600; }}
.empty {{ text-align: center; color: #484f58; padding: 40px; }}
.refresh {{ color: #8b949e; font-size: 12px; text-align: center; padding: 10px; }}
small {{ color: #484f58; font-size: 11px; }}
.source-bar {{ padding: 8px 24px; font-size: 13px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }}
.modal {{ display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 100; align-items: center; justify-content: center; }}
.modal.open {{ display: flex; }}
.modal-content {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; width: 420px; max-width: 90vw; }}
.modal-content h3 {{ color: #58a6ff; margin-bottom: 16px; }}
.modal-content label {{ display: block; font-size: 12px; color: #8b949e; margin-top: 10px; margin-bottom: 3px; }}
.modal-content input, .modal-content select {{ width: 100%; background: #0d1117; border: 1px solid #30363d; color: #e6edf3; padding: 8px; border-radius: 4px; font-size: 13px; }}
.modal-content input:focus {{ border-color: #58a6ff; outline: none; }}
.modal-actions {{ display: flex; gap: 8px; justify-content: flex-end; margin-top: 18px; }}
.msg {{ padding: 6px 12px; border-radius: 4px; font-size: 12px; margin-top: 8px; display: none; }}
.msg.success {{ background: #1a3a1a; color: #3fb950; display: block; }}
.msg.error {{ background: #3a1a1a; color: #f85149; display: block; }}
</style>
</head>
<body>
<div class="header">
  <div><h1>量化交易监控面板</h1></div>
  <div class="info">{now} | 交易日:{is_trading_day} | 状态:{market_status}</div>
</div>

<div class="source-bar">
  <div>{source_tag}</div>
  <div>{alipay_note}</div>
</div>

<div class="summary">
  <div class="summary-card"><div class="label">持仓数</div><div class="value" style="color:#58a6ff">{holdings_count}</div></div>
  <div class="summary-card"><div class="label">总市值</div><div class="value">¥{total_market_value:,.2f}</div></div>
  <div class="summary-card"><div class="label">投入本金</div><div class="value">¥{total_cost:,.2f}</div></div>
  <div class="summary-card"><div class="label">总盈亏</div><div class="value" style="color:{profit_color}">{total_profit:+,.2f}</div></div>
  <div class="summary-card"><div class="label">总收益率</div><div class="value" style="color:{profit_color}">{total_rate:+.2%}</div></div>
</div>

<div class="strategy">
  <div class="strategy-tag">亏损<span>{stop_add:.0f}%</span>停止加仓</div>
  <div class="strategy-tag">亏损<span>{stop_loss:.1f}%</span>止损</div>
  <div class="strategy-tag">盈利<span>{trigger:.0f}%</span>启动移动止盈</div>
  <div class="strategy-tag">最高回撤<span>{half:.0f}%</span>卖一半</div>
  <div class="strategy-tag">最高回撤<span>{all_pct:.0f}%</span>卖完</div>
</div>

<div class="section">
  <div class="section-title">基金持仓 ({holdings_count})</div>
  <div class="toolbar">
    <button class="btn btn-primary" onclick="openAddModal()">+ 手动添加</button>
    <button class="btn" onclick="document.getElementById('csvFile').click()">CSV 导入</button>
    <input type="file" id="csvFile" accept=".csv" style="display:none" onchange="importCsv(this)">
    <button class="btn btn-danger" onclick="clearAll()">清空持仓</button>
  </div>
  {holding_rows_table}
</div>

<div class="section">
  <div class="section-title">最近交易信号 ({decisions_count})</div>
  <div class="toolbar">
    <button class="btn btn-primary" onclick="evaluateStrategy()">策略评估</button>
    <button class="btn" onclick="sendReport()" style="border-color:#3fb950;color:#3fb950;">发送报告</button>
    <button class="btn btn-danger" onclick="clearDecisions()">清空信号</button>
    <button class="btn" onclick="testEmail()" style="border-color:#d29922;color:#d29922;">测试邮件</button>
  </div>
  {decision_rows_table}
</div>

<div class="refresh">页面刷新获取最新数据 | 量化交易系统 v1.0</div>

<!-- Add/Edit Modal -->
<div class="modal" id="editModal">
  <div class="modal-content">
    <h3 id="modalTitle">添加持仓</h3>
    <input type="hidden" id="editKey">
    <label>基金名称 *</label>
    <input type="text" id="editName" placeholder="例如: 摩根标普500指数(QDII)A">
    <label>基金代码 (可选)</label>
    <input type="text" id="editCode" placeholder="例如: 001156">
    <label>投入本金 *</label>
    <input type="number" id="editCost" placeholder="投入本金" step="0.01">
    <label>当前市值</label>
    <input type="number" id="editValue" placeholder="当前市值" step="0.01">
    <label>关联板块</label>
    <input type="text" id="editSector" placeholder="例如: 美股、稀土、量化">
    <div class="msg" id="editMsg"></div>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal()">取消</button>
      <button class="btn btn-primary" onclick="saveHolding()">保存</button>
    </div>
  </div>
</div>

<script>
function openAddModal() {{
    document.getElementById('modalTitle').textContent = '添加持仓';
    document.getElementById('editKey').value = '';
    document.getElementById('editName').value = '';
    document.getElementById('editCode').value = '';
    document.getElementById('editCost').value = '';
    document.getElementById('editValue').value = '';
    document.getElementById('editSector').value = '';
    document.getElementById('editMsg').className = 'msg';
    document.getElementById('editModal').classList.add('open');
}}
function editHolding(id, name, code, value, cost, sector) {{
    document.getElementById('modalTitle').textContent = '编辑持仓';
    document.getElementById('editKey').value = id;
    document.getElementById('editName').value = name;
    document.getElementById('editCode').value = (code && code.startsWith('__')) ? '' : code;
    document.getElementById('editCost').value = cost;
    document.getElementById('editValue').value = value;
    document.getElementById('editSector').value = sector || '';
    document.getElementById('editMsg').className = 'msg';
    document.getElementById('editModal').classList.add('open');
}}
function closeModal() {{ document.getElementById('editModal').classList.remove('open'); }}
function showMsg(cls, text) {{
    var m = document.getElementById('editMsg');
    m.className = 'msg ' + cls;
    m.textContent = text;
}}
async function saveHolding() {{
    var id = document.getElementById('editKey').value;
    var name = document.getElementById('editName').value.trim();
    var code = document.getElementById('editCode').value.trim();
    var cost = parseFloat(document.getElementById('editCost').value);
    var value = parseFloat(document.getElementById('editValue').value);
    var sector = document.getElementById('editSector').value.trim();
    if (!name || isNaN(cost)) {{ showMsg('error', '请填写基金名称和投入本金'); return; }}
    if (isNaN(value)) value = cost;
    var profit = value - cost;
    var profitRate = cost > 0 ? profit / cost : 0;
    var body = {{fund_name: name, fund_code: code, cost_amount: cost, market_value: value,
                 total_profit: profit, total_profit_rate: profitRate, sector_name: sector}};
    var url = '/api/holdings';
    var method = 'POST';
    if (id) {{ url = '/api/holdings/id/' + id; method = 'PUT'; }}
    var resp = await fetch(url, {{method: method, headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(body)}});
    var data = await resp.json();
    if (data.code === 0) {{ location.reload(); }}
    else {{ showMsg('error', data.msg || '保存失败'); }}
}}
async function deleteHolding(id) {{
    if (!confirm('确定删除该持仓?')) return;
    var resp = await fetch('/api/holdings/id/' + id, {{method: 'DELETE'}});
    var data = await resp.json();
    if (data.code === 0) location.reload(); else alert(data.msg);
}}
async function clearAll() {{
    if (!confirm('确定清空所有持仓?')) return;
    var resp = await fetch('/api/holdings/clear', {{method: 'POST'}});
    var data = await resp.json();
    if (data.code === 0) location.reload(); else alert(data.msg);
}}
async function importCsv(input) {{
    var file = input.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append('file', file);
    var resp = await fetch('/api/holdings/import_csv', {{method: 'POST', body: formData}});
    var data = await resp.json();
    if (data.code === 0) location.reload(); else alert(data.msg);
    input.value = '';
}}
async function evaluateStrategy() {{
    var resp = await fetch('/api/evaluate', {{method: 'POST'}});
    var data = await resp.json();
    if (data.code === 0) location.reload(); else alert(data.msg || '评估失败');
}}
async function clearDecisions() {{
    if (!confirm('确定清空所有交易信号?')) return;
    var resp = await fetch('/api/decisions/clear', {{method: 'POST'}});
    var data = await resp.json();
    if (data.code === 0) location.reload(); else alert(data.msg);
}}
async function testEmail() {{
    var resp = await fetch('/api/email/test', {{method: 'POST'}});
    var data = await resp.json();
    alert(data.code === 0 ? data.msg : (data.msg || '发送失败'));
}}
async function sendReport() {{
    var resp = await fetch('/api/report/send', {{method: 'POST'}});
    var data = await resp.json();
    alert(data.code === 0 ? data.msg : (data.msg || '发送失败'));
}}
</script>
</body>
</html>"""

# 用占位符替换table内容
HTML_TEMPLATE = HTML_TEMPLATE.replace("{holding_rows_table}",
    '<table><tr><th>基金名称</th><th>市值</th><th>本金</th><th>累计盈亏</th><th>收益率</th><th>板块</th><th>状态</th><th>操作</th></tr>{holding_rows}</table>'
).replace("{decision_rows_table}",
    '<table><tr><th></th><th>基金</th><th>收益率</th><th>操作建议</th><th>原因</th><th>时间</th></tr>{decision_rows}</table>')


@app.route("/api/holdings", methods=["GET"])
def get_holdings():
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
        result = []
        for h in holdings:
            result.append({
                "id": h.id,
                "fund_code": h.fund_code,
                "fund_name": h.fund_name,
                "shares": h.shares,
                "cost_amount": h.cost_amount,
                "avg_cost": h.avg_cost,
                "current_nav": h.current_nav,
                "market_value": h.market_value,
                "daily_profit": h.daily_profit,
                "total_profit": h.total_profit,
                "total_profit_rate": h.total_profit_rate,
                "peak_return_rate": h.peak_return_rate,
                "trailing_stop_active": h.trailing_stop_active,
                "status": h.status,
                "sector_name": h.sector_name,
                "sector_code": h.sector_code,
                "sector_change_pct": h.sector_change_pct,
                "updated_at": h.updated_at.isoformat() if h.updated_at else "",
            })
        return jsonify({"code": 0, "data": result, "total": len(result)})
    except Exception as e:
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/holdings", methods=["POST"])
def add_holding():
    data = request.json
    if not data:
        return jsonify({"code": -1, "msg": "请求体为空"}), 400

    db = SessionLocal()
    try:
        fund_code = data.get("fund_code", "")
        fund_name = data.get("fund_name", "")
        if not fund_code and fund_name:
            fund_code = f"__{fund_name}"

        existing = db.query(Holding).filter(Holding.fund_code == fund_code).first()
        if not existing and fund_name:
            existing = db.query(Holding).filter(Holding.fund_name == fund_name).first()
        if existing:
            return jsonify({"code": -1, "msg": f"该基金已存在"}), 400

        cost = float(data.get("cost_amount", 0))
        mv = float(data.get("market_value", cost))
        holding = Holding(
            fund_code=fund_code,
            fund_name=fund_name,
            shares=0,
            cost_amount=cost,
            avg_cost=0,
            market_value=mv,
            total_profit=mv - cost,
            total_profit_rate=(mv - cost) / cost if cost > 0 else 0,
            sector_name=data.get("sector_name", ""),
            status="holding",
        )
        db.add(holding)

        st = StrategyState(
            fund_code=fund_code,
            entry_date=datetime.now().strftime("%Y-%m-%d"),
            position_status="full",
            can_add_position=True,
        )
        db.add(st)

        db.commit()
        return jsonify({"code": 0, "msg": "添加成功"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/holdings", methods=["DELETE"])
def delete_holding_by_body():
    """通过 JSON body 中的 fund_code 或 fund_name 删除"""
    data = request.json or {}
    key = data.get("fund_code") or data.get("fund_name", "")
    if not key:
        return jsonify({"code": -1, "msg": "缺少 fund_code 或 fund_name"}), 400
    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(
            (Holding.fund_code == key) | (Holding.fund_name == key)
        ).first()
        if holding:
            db.delete(holding)
            db.query(StrategyState).filter(StrategyState.fund_code == holding.fund_code).delete()
            db.commit()
        return jsonify({"code": 0, "msg": "删除成功"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()




@app.route("/api/holdings/<fund_code>", methods=["PUT"])
def update_holding(fund_code):
    data = request.json
    if not data:
        return jsonify({"code": -1, "msg": "请求体为空"}), 400

    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(Holding.fund_code == fund_code).first()
        if not holding:
            return jsonify({"code": -1, "msg": "基金不存在"}), 404

        for key in ["fund_name", "shares", "cost_amount", "avg_cost", "status"]:
            if key in data:
                val = data[key]
                if key in ("shares", "cost_amount", "avg_cost"):
                    val = float(val)
                setattr(holding, key, val)

        db.commit()
        return jsonify({"code": 0, "msg": "更新成功"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/holdings/<fund_code>", methods=["DELETE"])
def delete_holding(fund_code):
    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(Holding.fund_code == fund_code).first()
        if holding:
            db.delete(holding)
            db.query(StrategyState).filter(StrategyState.fund_code == fund_code).delete()
            db.commit()
        return jsonify({"code": 0, "msg": "删除成功"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/holdings/id/<int:holding_id>", methods=["PUT"])
def update_holding_by_id(holding_id):
    """通过 id 更新持仓, 自动重算盈亏"""
    data = request.json
    if not data:
        return jsonify({"code": -1, "msg": "请求体为空"}), 400

    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(Holding.id == holding_id).first()
        if not holding:
            return jsonify({"code": -1, "msg": "持仓不存在"}), 404

        for key in ["fund_name", "fund_code", "sector_name", "status"]:
            if key in data:
                setattr(holding, key, data[key])

        cost = data.get("cost_amount")
        mv = data.get("market_value")
        if cost is not None:
            holding.cost_amount = float(cost)
        if mv is not None:
            holding.market_value = float(mv)

        tp = data.get("total_profit")
        if tp is not None:
            holding.total_profit = float(tp)
        else:
            holding.total_profit = holding.market_value - holding.cost_amount

        pr = data.get("total_profit_rate")
        if pr is not None:
            holding.total_profit_rate = float(pr)
        elif holding.cost_amount > 0:
            holding.total_profit_rate = holding.total_profit / holding.cost_amount

        if holding.fund_code and not holding.fund_code.startswith("__"):
            st = db.query(StrategyState).filter(StrategyState.fund_code == holding.fund_code).first()
            if not st:
                st = StrategyState(
                    fund_code=holding.fund_code,
                    entry_date=datetime.now().strftime("%Y-%m-%d"),
                    position_status="full",
                    can_add_position=True,
                )
                db.add(st)

        db.commit()
        return jsonify({"code": 0, "msg": "更新成功"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/holdings/id/<int:holding_id>", methods=["DELETE"])
def delete_holding_by_id(holding_id):
    """通过 id 删除持仓"""
    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(Holding.id == holding_id).first()
        if holding:
            fund_code = holding.fund_code
            db.delete(holding)
            if fund_code:
                db.query(StrategyState).filter(StrategyState.fund_code == fund_code).delete()
            db.commit()
        return jsonify({"code": 0, "msg": "删除成功"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/holdings/clear", methods=["POST"])
def clear_holdings():
    """清空所有持仓 (用于清除错误抓取的持仓)"""
    db = SessionLocal()
    try:
        count = db.query(Holding).count()
        db.query(Holding).delete()
        db.query(StrategyState).delete()
        db.query(Decision).delete()
        db.commit()
        return jsonify({"code": 0, "msg": f"已清空 {count} 条持仓及关联数据"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/holdings/refresh", methods=["POST"])
def refresh_holdings():
    """手动刷新持仓净值和板块数据"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
        if not holdings:
            return jsonify({"code": 0, "msg": "无持仓数据", "data": []})

        codes = [h.fund_code for h in holdings]
        nav_data = FundDataService.get_fund_realtime_batch(codes)

        sector_codes = list(set(h.sector_code for h in holdings if h.sector_code))
        sector_data = FundDataService.get_sector_realtime_batch(sector_codes)

        updated = []
        for h in holdings:
            nd = nav_data.get(h.fund_code)
            if nd:
                h.current_nav = nd.get("estimated_nav", nd.get("nav", 0))
                if h.current_nav > 0 and h.shares > 0:
                    h.market_value = h.shares * h.current_nav
                    h.total_profit = h.market_value - h.cost_amount
                    h.total_profit_rate = h.total_profit / h.cost_amount if h.cost_amount > 0 else 0

            if h.sector_code and h.sector_code in sector_data:
                h.sector_change_pct = sector_data[h.sector_code].get("change_pct", 0)

            updated.append({
                "fund_code": h.fund_code,
                "fund_name": h.fund_name,
                "current_nav": h.current_nav,
                "market_value": h.market_value,
                "total_profit": h.total_profit,
                "total_profit_rate": h.total_profit_rate,
                "sector_change_pct": h.sector_change_pct,
            })

        db.commit()
        return jsonify({"code": 0, "msg": "刷新成功", "data": updated})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/evaluate", methods=["POST"])
def evaluate_strategy():
    """手动触发策略评估"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
        if not holdings:
            return jsonify({"code": 0, "msg": "无持仓数据", "data": []})

        # 删除当天旧决策 (按 fund_name)
        today = datetime.now().strftime("%Y-%m-%d")
        for h in holdings:
            db.query(Decision).filter(
                Decision.fund_name == h.fund_name,
                Decision.created_at >= f"{today} 00:00:00"
            ).delete(synchronize_session=False)
        db.flush()

        results = []
        for h in holdings:
            st = db.query(StrategyState).filter(StrategyState.fund_code == h.fund_code).first()
            if not st:
                st = StrategyState(
                    fund_code=h.fund_code,
                    entry_nav=h.cost_amount,
                    highest_return_rate=h.total_profit_rate or 0,
                    position_status="full",
                )
                db.add(st)
                db.flush()

            result = strategy_engine.evaluate(
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

            # 持仓状态只保留简单值, 不写入策略建议文本
            simple_status = {
                "stop_loss": "已卖出", "sell_all": "已卖出", "sell_half": "已卖出",
                "observe": "观察",
            }.get(result["action"], "持有")
            h.status = simple_status
            h.peak_return_rate = st.highest_return_rate
            h.trailing_stop_active = st.trailing_active

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

            results.append({
                "fund_code": h.fund_code,
                "fund_name": h.fund_name,
                "current_return_rate": result["current_return_rate"],
                "decision": result["decision"],
                "reason": result["reason"],
                "action": result["action"],
                "alert_level": result["alert_level"],
            })

        db.commit()
        return jsonify({"code": 0, "msg": "评估完成", "data": results})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/decisions", methods=["GET"])
def get_decisions():
    db = SessionLocal()
    try:
        limit = request.args.get("limit", 50, type=int)
        decisions = db.query(Decision).order_by(Decision.created_at.desc()).limit(limit).all()
        result = []
        for d in decisions:
            result.append({
                "id": d.id,
                "fund_code": d.fund_code,
                "fund_name": d.fund_name,
                "decision": d.decision,
                "reason": d.reason,
                "action": d.action,
                "current_return_rate": d.current_return_rate,
                "peak_return_rate": d.peak_return_rate,
                "current_nav": d.current_nav,
                "sector_change_pct": d.sector_change_pct,
                "created_at": d.created_at.isoformat() if d.created_at else "",
            })
        return jsonify({"code": 0, "data": result})
    except Exception as e:
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/decisions/clear", methods=["POST"])
def clear_decisions():
    """清空所有交易信号"""
    db = SessionLocal()
    try:
        count = db.query(Decision).count()
        db.query(Decision).delete()
        db.commit()
        return jsonify({"code": 0, "msg": f"已清空 {count} 条信号"})
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": str(e)}), 500
    finally:
        db.close()


@app.route("/api/email/test", methods=["POST"])
def test_email():
    """测试邮件发送 (纯文本, 不读DB)"""
    try:
        recipient = Config.QQ_EMAIL
        if not recipient:
            return jsonify({"code": 1, "msg": "测试邮件发送失败：未配置 QQ_EMAIL"})
        if not Config.QQ_EMAIL_AUTH_CODE:
            return jsonify({"code": 1, "msg": "测试邮件发送失败：未配置 QQ_EMAIL_AUTH_CODE"})

        import smtplib
        from email.mime.text import MIMEText
        from email.header import Header

        msg = MIMEText("如果收到这封邮件，说明 QQ 邮箱 SMTP 配置成功。", "plain", "utf-8")
        msg["From"] = recipient
        msg["To"] = recipient
        msg["Subject"] = Header("量化基金系统测试邮件", "utf-8")

        with smtplib.SMTP("smtp.qq.com", 587, timeout=30) as server:
            server.starttls()
            server.login(recipient, Config.QQ_EMAIL_AUTH_CODE)
            server.sendmail(recipient, recipient, msg.as_string())

        return jsonify({"code": 0, "msg": "测试邮件发送成功"})
    except Exception as e:
        return jsonify({"code": 1, "msg": f"测试邮件发送失败：{e}"})


@app.route("/api/report/send", methods=["POST"])
def send_report():
    """发送完整每日基金决策报告"""
    from email_sender import EmailSender
    sender = EmailSender()
    recipient = Config.QQ_EMAIL
    if not recipient or not Config.QQ_EMAIL_AUTH_CODE:
        return jsonify({"code": 1, "msg": "未配置 QQ_EMAIL / QQ_EMAIL_AUTH_CODE"})

    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
        if not holdings:
            return jsonify({"code": 1, "msg": "无持仓数据，请先导入持仓"})

        holdings_data = []
        for h in holdings:
            holdings_data.append({
                "fund_name": h.fund_name,
                "fund_code": h.fund_code,
                "market_value": h.market_value,
                "cost_amount": h.cost_amount,
                "total_profit": h.total_profit or 0,
                "total_profit_rate": h.total_profit_rate or 0,
                "current_nav": h.current_nav,
                "sector_name": h.sector_name or "",
                "sector_change_pct": h.sector_change_pct or 0,
            })

        subq = db.query(
            Decision.fund_name,
            func.max(Decision.id).label("max_id")
        ).group_by(Decision.fund_name).subquery()
        decisions_db = db.query(Decision).join(
            subq, and_(Decision.id == subq.c.max_id)
        ).order_by(Decision.created_at.desc()).all()
        decisions_data = [{
            "fund_name": d.fund_name,
            "fund_code": d.fund_code,
            "current_return_rate": d.current_return_rate or 0,
            "decision": d.decision,
            "reason": d.reason,
            "action": d.action,
            "alert_level": "normal",
        } for d in decisions_db]

        ok = sender.send_full_report(recipient, holdings_data, decisions_data)
        if ok:
            return jsonify({"code": 0, "msg": "报告邮件发送成功"})
        else:
            return jsonify({"code": 1, "msg": "报告邮件发送失败：SMTP 错误"})
    except Exception as e:
        return jsonify({"code": 1, "msg": f"报告邮件发送失败：{e}"}), 500
    finally:
        db.close()


@app.route("/api/sector/<fund_code>", methods=["GET"])
def get_fund_sector(fund_code):
    """获取基金的关联板块实时数据"""
    sector_info = Config.FUND_SECTOR_MAP.get(fund_code, {})
    if not sector_info:
        return jsonify({"code": -1, "msg": "未找到该基金的板块映射"}), 404

    result = {"fund_code": fund_code, "sector_name": sector_info.get("name", "")}

    sector_code = sector_info.get("sector_code", "")
    if sector_code:
        sector_data = FundDataService.get_sector_realtime(sector_code)
        if sector_data:
            result["sector"] = sector_data

    index_code = sector_info.get("index_code", "")
    if index_code:
        index_data = FundDataService.get_index_realtime(index_code)
        if index_data:
            result["index"] = index_data

    return jsonify({"code": 0, "data": result})


@app.route("/api/market/trading_day", methods=["GET"])
def check_trading_day():
    is_td = FundDataService.is_trading_day()
    is_open = FundDataService.is_market_open()
    return jsonify({
        "code": 0,
        "data": {
            "is_trading_day": is_td,
            "is_market_open": is_open,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
    })


@app.route("/api/config/strategy", methods=["GET"])
def get_strategy_config():
    return jsonify({
        "code": 0,
        "data": {
            "stop_add_loss_rate": Config.STOP_ADD_LOSS_RATE,
            "stop_loss_rate": Config.STOP_LOSS_RATE,
            "trailing_stop_trigger": Config.TRAILING_STOP_TRIGGER,
            "trailing_drawdown_half": Config.TRAILING_DRAWDOWN_HALF,
            "trailing_drawdown_all": Config.TRAILING_DRAWDOWN_ALL,
        }
    })


@app.route("/api/holdings/import_csv", methods=["POST"])
def import_csv():
    """CSV 导入持仓"""
    if not Config.ENABLE_CSV_IMPORT:
        return jsonify({"code": -1, "msg": "CSV导入已禁用"}), 403

    if "file" not in request.files:
        return jsonify({"code": -1, "msg": "未上传文件"}), 400

    file = request.files["file"]
    try:
        content = file.read().decode("utf-8-sig")
    except Exception as e:
        return jsonify({"code": -1, "msg": f"文件编码错误: {e}"}), 400

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return jsonify({"code": -1, "msg": "CSV无表头"}), 400

    db = SessionLocal()
    imported = 0
    updated = 0
    errors = []

    for row_num, row in enumerate(reader, start=2):
        fund_name = (row.get("fund_name") or "").strip()
        if not fund_name:
            errors.append(f"行{row_num}: 缺少基金名称")
            continue

        fund_code = (row.get("fund_code") or "").strip()
        if not fund_code:
            fund_code = f"__{fund_name}"

        try:
            current_value = float(row.get("current_value", 0) or 0)
            cost_amount = float(row.get("cost_amount", 0) or 0)
            profit_rate_str = (row.get("profit_rate") or "").strip()
            sector_name = (row.get("sector_name") or "").strip()

            # 从 current_value 和 cost_amount 重新计算盈亏 (最可靠)
            recalc_profit = current_value - cost_amount
            recalc_rate = recalc_profit / cost_amount if cost_amount > 0 else 0.0

            # CSV 提供的 profit_rate 仅作为参考
            csv_rate = None
            if profit_rate_str:
                try:
                    if profit_rate_str.endswith("%"):
                        csv_rate = float(profit_rate_str[:-1]) / 100.0
                    else:
                        r = float(profit_rate_str)
                        csv_rate = r / 100.0 if abs(r) > 1.0 else r
                except ValueError:
                    pass
        except ValueError as e:
            errors.append(f"行{row_num}: 数字解析错误 - {e}")
            continue

        try:
            existing = db.query(Holding).filter(
                (Holding.fund_code == fund_code) | (Holding.fund_name == fund_name)
            ).first()

            if existing:
                if fund_code and not fund_code.startswith("__"):
                    existing.fund_code = fund_code
                existing.fund_name = fund_name
                existing.cost_amount = cost_amount
                existing.market_value = current_value
                existing.total_profit = recalc_profit
                existing.total_profit_rate = recalc_rate
                existing.sector_name = sector_name
                existing.status = "holding"
                updated += 1
            else:
                holding = Holding(
                    fund_code=fund_code,
                    fund_name=fund_name,
                    shares=0,
                    cost_amount=cost_amount,
                    avg_cost=0,
                    market_value=current_value,
                    total_profit=recalc_profit,
                    total_profit_rate=recalc_rate,
                    sector_name=sector_name,
                    status="holding",
                )
                db.add(holding)

                st = StrategyState(
                    fund_code=fund_code,
                    entry_date=datetime.now().strftime("%Y-%m-%d"),
                    position_status="full",
                    can_add_position=True,
                )
                db.add(st)
                imported += 1
        except Exception as e:
            errors.append(f"行{row_num}: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"code": -1, "msg": f"数据库错误: {e}"}), 500
    finally:
        db.close()

    msg = f"导入 {imported} 条, 更新 {updated} 条"
    if errors:
        msg += f", 错误: {'; '.join(errors[:5])}"
    return jsonify({"code": 0, "msg": msg, "imported": imported, "updated": updated})


@app.route("/api/config/data_source", methods=["GET"])
def get_data_source():
    return jsonify({
        "code": 0,
        "data": {
            "holding_source": Config.HOLDING_SOURCE,
            "auto_alipay_scrape": Config.AUTO_ALIPAY_SCRAPE,
            "enable_manual_import": Config.ENABLE_MANUAL_IMPORT,
            "enable_csv_import": Config.ENABLE_CSV_IMPORT,
            "auto_import_confirm": Config.AUTO_IMPORT_CONFIRM,
        }
    })


@app.route("/api/alipay/test_parse", methods=["POST"])
def alipay_test_parse():
    """支付宝解析测试 (仅返回结果, 不写库)"""
    if not Config.AUTO_ALIPAY_SCRAPE:
        return jsonify({"code": -1, "msg": "支付宝自动抓取未启用"}), 403
    try:
        from alipay_scraper import AlipayScraper
        scraper = AlipayScraper()
        valid = scraper.test_parse_current_screen()
        return jsonify({"code": 0, "data": [{
            "fund_name": h["fund_name"],
            "current_value": h.get("current_value"),
            "profit_amount": h.get("profit_amount"),
            "profit_rate": h.get("profit_rate"),
        } for h in valid]})
    except Exception as e:
        return jsonify({"code": -1, "msg": str(e)}), 500


@app.route("/api/alipay/fetch_candidate", methods=["POST"])
def alipay_fetch_candidate():
    """获取支付宝识别候选 (不确认, 不写库)"""
    if not Config.AUTO_ALIPAY_SCRAPE:
        return jsonify({"code": -1, "msg": "支付宝自动抓取未启用"}), 403
    try:
        from alipay_scraper import AlipayScraper
        scraper = AlipayScraper()
        holdings = scraper.fetch_holdings()
        return jsonify({"code": 0, "data": holdings, "total": len(holdings)})
    except Exception as e:
        return jsonify({"code": -1, "msg": str(e)}), 500


@app.route("/api/alipay/confirm_import", methods=["POST"])
def alipay_confirm_import():
    """确认支付宝候选并写入数据库"""
    if not Config.AUTO_ALIPAY_SCRAPE:
        return jsonify({"code": -1, "msg": "支付宝自动抓取未启用"}), 403
    data = request.json or {}
    holdings = data.get("holdings", [])
    if not holdings or len(holdings) < 6:
        return jsonify({"code": -1, "msg": f"无效数据 ({len(holdings)} 条, 需≥6)"}), 400
    from scheduler import FundScheduler
    sched = FundScheduler.__new__(FundScheduler)
    try:
        sched._merge_holdings_to_db(holdings)
        return jsonify({"code": 0, "msg": f"已写入 {len(holdings)} 条持仓"})
    except Exception as e:
        return jsonify({"code": -1, "msg": str(e)}), 500


if __name__ == "__main__":
    init_db()
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
