import requests
import json
import re
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List


class FundDataService:

    @staticmethod
    def get_fund_realtime_nav(fund_code: str) -> Optional[dict]:
        """获取基金实时估值 (东方财富)"""
        url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
        headers = {
            "Referer": "http://fund.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = "utf-8"
            text = resp.text
            match = re.search(r"jsonpgz\((.+)\)", text)
            if match:
                data = json.loads(match.group(1))
                return {
                    "fund_code": data.get("fundcode", ""),
                    "fund_name": data.get("name", ""),
                    "nav": float(data.get("dwjz", 0)),
                    "estimated_nav": float(data.get("gsz", 0)),
                    "estimated_change_pct": float(data.get("gszzl", 0)),
                    "nav_date": data.get("jzrq", ""),
                    "update_time": data.get("gztime", ""),
                }
        except Exception as e:
            print(f"[FundData] 获取基金 {fund_code} 实时数据失败: {e}")
        return None

    @staticmethod
    def get_fund_realtime_batch(fund_codes: List[str]) -> Dict[str, dict]:
        """批量获取多只基金实时估值"""
        result = {}
        codes_str = ",".join(fund_codes)
        url = f"http://fundgz.1234567.com.cn/js/{codes_str}.js"
        headers = {
            "Referer": "http://fund.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = "utf-8"
            text = resp.text

            for code in fund_codes:
                url_single = f"http://fundgz.1234567.com.cn/js/{code}.js"
                try:
                    r = requests.get(url_single, headers=headers, timeout=10)
                    r.encoding = "utf-8"
                    match = re.search(r"jsonpgz\((.+)\)", r.text)
                    if match:
                        data = json.loads(match.group(1))
                        result[code] = {
                            "fund_code": data.get("fundcode", ""),
                            "fund_name": data.get("name", ""),
                            "nav": float(data.get("dwjz", 0)),
                            "estimated_nav": float(data.get("gsz", 0)),
                            "estimated_change_pct": float(data.get("gszzl", 0)),
                            "nav_date": data.get("jzrq", ""),
                            "update_time": data.get("gztime", ""),
                        }
                except Exception:
                    pass
        except Exception as e:
            print(f"[FundData] 批量获取失败, 逐个获取: {e}")
            for code in fund_codes:
                single = FundDataService.get_fund_realtime_nav(code)
                if single:
                    result[code] = single
        return result

    @staticmethod
    def get_sector_realtime(sector_code: str) -> Optional[dict]:
        """获取板块实时涨跌幅 (东方财富)"""
        if not sector_code:
            return None
        try:
            url = "http://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": "1", "pz": "20", "po": "1", "np": "1",
                "fltt": "2", "invt": "2",
                "fid": "f3", "fs": f"m:90+t2+f3!50",
                "fields": "f2,f3,f4,f12,f14",
                "fid": "f3"
            }
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://quote.eastmoney.com/"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()
            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    if item.get("f12") == sector_code:
                        return {
                            "sector_code": item.get("f12", ""),
                            "sector_name": item.get("f14", ""),
                            "price": float(item.get("f2", 0)),
                            "change_pct": float(item.get("f3", 0)),
                        }
        except Exception as e:
            print(f"[FundData] 获取板块 {sector_code} 数据失败: {e}")
        return None

    @staticmethod
    def get_sector_realtime_batch(sector_codes: List[str]) -> Dict[str, dict]:
        """批量获取板块实时数据"""
        result = {}
        if not sector_codes:
            return result
        valid_codes = [c for c in sector_codes if c]
        if not valid_codes:
            return result
        try:
            url = "http://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": "1", "pz": "100", "po": "1", "np": "1",
                "fltt": "2", "invt": "2",
                "fid": "f3", "fs": "m:90+t2+f3!50",
                "fields": "f2,f3,f4,f12,f14"
            }
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://quote.eastmoney.com/"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()
            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    code = item.get("f12", "")
                    if code in valid_codes:
                        result[code] = {
                            "sector_code": code,
                            "sector_name": item.get("f14", ""),
                            "price": float(item.get("f2", 0)),
                            "change_pct": float(item.get("f3", 0)),
                        }
        except Exception as e:
            print(f"[FundData] 批量获取板块数据失败: {e}")
            for code in valid_codes:
                single = FundDataService.get_sector_realtime(code)
                if single:
                    result[code] = single
        return result

    @staticmethod
    def get_index_realtime(index_code: str) -> Optional[dict]:
        """获取指数实时数据"""
        if not index_code:
            return None
        try:
            url = "http://push2.eastmoney.com/api/qt/stock/get"
            params = {
                "secid": f"1.{index_code}" if index_code.startswith("0") or index_code.startswith("3") else f"0.{index_code}",
                "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170"
            }
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://quote.eastmoney.com/"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()
            if data.get("data"):
                d = data["data"]
                return {
                    "index_code": index_code,
                    "price": float(d.get("f43", 0) or 0) / 100,
                    "change_pct": float(d.get("f170", 0) or 0) / 100 if d.get("f170") else float(d.get("f169", 0) or 0) / 100,
                }
        except Exception as e:
            print(f"[FundData] 获取指数 {index_code} 数据失败: {e}")
        return None

    @staticmethod
    def get_fund_hist_nav(fund_code: str, days: int = 60) -> List[dict]:
        """获取基金历史净值"""
        try:
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            if df is not None and not df.empty:
                df = df.tail(days)
                result = []
                for _, row in df.iterrows():
                    result.append({
                        "date": str(row.iloc[0])[:10],
                        "nav": float(row.iloc[1]),
                    })
                return result
        except Exception as e:
            print(f"[FundData] 获取基金 {fund_code} 历史净值失败: {e}")
        return []

    @staticmethod
    def get_fund_detail(fund_code: str) -> Optional[dict]:
        """获取基金基本信息"""
        try:
            df = ak.fund_individual_basic_info_xq(symbol=fund_code)
            if df is not None and not df.empty:
                row = df.iloc[0]
                return {
                    "fund_code": fund_code,
                    "fund_name": str(row.get("基金名称", "")),
                    "fund_type": str(row.get("基金类型", "")),
                }
        except Exception:
            pass

        nav_data = FundDataService.get_fund_realtime_nav(fund_code)
        if nav_data:
            return {
                "fund_code": fund_code,
                "fund_name": nav_data.get("fund_name", ""),
                "fund_type": "",
            }
        return None

    @staticmethod
    def is_trading_day() -> bool:
        """判断今天是否为A股交易日 (简易判断: 周一至周五, 排除常见节假日)"""
        today = datetime.now()
        if today.weekday() >= 5:
            return False
        try:
            df = ak.tool_trade_date_hist_sina()
            today_str = today.strftime("%Y-%m-%d")
            if df is not None and not df.empty:
                dates = df["trade_date"].astype(str).tolist()
                return today_str in dates
        except Exception:
            pass
        return today.weekday() < 5

    @staticmethod
    def is_market_open() -> bool:
        """判断当前是否在交易时间"""
        from config import Config
        now = datetime.now().time()
        today = datetime.now()
        if today.weekday() >= 5:
            return False
        morning_open = datetime.strptime(Config.TRADING_HOURS["morning_open"], "%H:%M").time()
        morning_close = datetime.strptime(Config.TRADING_HOURS["morning_close"], "%H:%M").time()
        afternoon_open = datetime.strptime(Config.TRADING_HOURS["afternoon_open"], "%H:%M").time()
        afternoon_close = datetime.strptime(Config.TRADING_HOURS["afternoon_close"], "%H:%M").time()
        return (morning_open <= now <= morning_close) or (afternoon_open <= now <= afternoon_close)
