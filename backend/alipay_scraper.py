import os
import re
import time
import json
import subprocess
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
from config import Config

"""
支付宝基金持仓自动抓取模块

持有页结构: 列表页不显示6位基金代码, 每行:
  左侧: 基金名称
  右侧上: 金额 / 昨日收益
  右侧下: 持有收益 / 持有收益率

严格规则:
- 基金名长度>=5 且包含关键词 (混合/指数/债券/ETF/QDII/联接/股票/基金/量化/制造/纳斯达克/标普/中证)
- 排除分类标签: 全部/偏股/偏债/黄金/全球/指数+/自选/持有 等
- 金额>10元才录入
- <5只基金判定失败, 进入手动录入
-- auto import needs user 'y' confirmation
"""

ALIPAY_PACKAGE = "com.eg.android.AlipayGphone"
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "chrome_profile", "debug")

# 必须包含至少一个关键词才算基金名
FUND_NAME_KEYWORDS = [
    "混合", "指数", "债券", "ETF", "QDII", "联接",
    "股票", "基金", "量化", "制造", "纳斯达克", "标普", "中证",
    "低碳", "稀土",
]

# 明确不是基金名的标签/按钮/UI文字
BLOCKED_NAMES = {
    "全部", "偏股", "偏债", "指数+", "指数", "黄金", "全球",
    "基金市场", "机会", "自选", "持有", "我的持有",
    "金额", "昨日收益", "持有收益", "收益率", "持有收益率",
    "去看看", "为你追踪", "定投", "热门", "搜索",
    "支付宝", "理财", "首页", "消息", "我的",
    "买入", "卖出", "转换", "赎回", "申购", "分红",
    "日收益", "净值", "份额", "持仓",
    "加自选", "分享", "更多", "筛选", "排序",
    "暂无持仓", "立即添加",
    "累计收益", "本月收益",
    "混合型", "债券型", "股票型", "货币型", "指数型",
    "宽基", "窄基", "行业", "主题", "QDII型", "FOF型",
    "LOF", "FOF", "货币",
    "今日收益更新", "答题有礼", "去分析", "金选指数基金",
    "名称", "昨日", "今日", "去看看分析", "立即去切换",
}

# 持有页面验证关键词 (至少有2个才认为页面正确)
HOLDINGS_PAGE_MARKERS = [
    "我的持有", "金额", "昨日收益", "持有收益",
    "持有收益率", "基金市场", "持有",
]

# 底部导航关键字
BOTTOM_NAV_TEXTS = {"基金市场", "机会", "自选", "持有"}

# 模拟器/系统干扰
NOISE_PATTERNS = [
    "雷电模拟器", "雷电游戏", "火影忍者", "系统应用",
    "支付宝宝", "设置", "相机", "相册", "文件管理",
    "浏览器", "时钟", "计算器", "日历", "天气", "音乐",
    "下载", "图库", "联系人", "电话", "短信",
    "一键", "清理", "蚂蚁森林", "蚂蚁庄园", "余额宝",
    "花呗", "借呗", "信用卡", "手机充值", "转账", "红包",
    "扫一扫", "收付款", "出行", "市民中心",
]

# 已知基金白名单 (从 config 读取, 在 .env 的 KNOWN_FUNDS 中配置)
KNOWN_FUNDS = Config.KNOWN_FUNDS

# 财富号/广告行关键词块 (包含任一词即丢弃)
WEALTH_KEYWORDS = {
    "财富", "财富号", "答题有礼", "答题", "今日收益更新",
    "去分析", "怎么投", "@", "HoL", "金选",
    "基金财富", "金财", "财号", "财富号>", "财富号》",
    "如收益", "实该基金", "报告", "走势", "生成", "析看分现",
    "持仓解码", "你持有的基金", "近一月表现", "申赎指南",
}


class AlipayScraper:

    LDPLAYER_SEARCH_PATHS = [
        r"C:\LDPlayer\LDPlayer9", r"D:\LDPlayer\LDPlayer9",
        r"C:\leidian\LDPlayer9", r"D:\leidian\LDPlayer9",
        r"C:\Program Files\ldplayer9", r"D:\Program Files\ldplayer9",
        r"C:\LDPlayer", r"D:\LDPlayer",
    ]

    def __init__(self):
        self.adb_path: Optional[str] = None
        self.device_addr: Optional[str] = None
        self.screen_w: int = 0
        self.screen_h: int = 0
        os.makedirs(DEBUG_DIR, exist_ok=True)

    # ==================== 入口 ====================

    def fetch_holdings(self) -> List[dict]:
        print("\n" + "=" * 60)
        print("[Alipay] 开始获取支付宝基金持仓...")
        print("=" * 60)

        if not self._connect_emulator():
            print("[Alipay] 无法连接模拟器")
            return []

        if not self._get_screen_size():
            print("[Alipay] 屏幕尺寸异常")
            return []

        try:
            import uiautomator2 as u2
            d = u2.connect(self.device_addr)
            self._u2_ensure_initialized(d)
        except Exception as e:
            print(f"[Alipay] uiautomator2 连接失败: {e}")
            return []

        try:
            d.app_start(ALIPAY_PACKAGE)
            time.sleep(3)
            if not self._u2_navigate_to_holdings(d):
                print("[Alipay] 导航到持有页失败")
                return []

            holdings = self._u2_extract_from_holdings_page(d)
            d.press("home")
        except Exception as e:
            print(f"[Alipay] 自动抓取出错: {e}")
            import traceback
            traceback.print_exc()
            try:
                d.press("home")
            except Exception:
                pass
            holdings = []
        finally:
            try:
                d.app_stop(ALIPAY_PACKAGE)
            except Exception:
                pass

        valid = [h for h in holdings if self._is_valid_holding(h)]
        complete = [h for h in valid
                    if h.get("profit_amount") is not None
                    and h.get("profit_rate") is not None]

        print(f"\n[Alipay] ====== 解析结果 ({len(valid)} 只有效, {len(complete)} 只完整) ======")
        for i, h in enumerate(valid, 1):
            pa = h.get("profit_amount")
            pr = h.get("profit_rate")
            pa_str = f"{pa:+.2f}" if pa is not None else "None"
            pr_str = f"{pr*100:.2f}%" if pr is not None else "None"
            print(f"  {i}. {h['fund_name']} | 金额={h.get('current_value', 0):.2f} "
                  f"| 收益={pa_str} "
                  f"| 收益率={pr_str}")
        print("[Alipay] ====== 结果结束 ======\n")

        threshold = min(6, len(KNOWN_FUNDS))
        if len(valid) < threshold:
            print(f"[Alipay] 仅识别 {len(valid)} 只基金 (<{threshold}), 判定失败")
            return []

        missing_profit = [h for h in valid
                          if h.get("profit_amount") is None
                          or h.get("profit_rate") is None]
        if missing_profit:
            names = ", ".join(h["fund_name"] for h in missing_profit)
            print(f"[Alipay] {len(missing_profit)} 只基金收益缺失: {names}, 判定失败")
            return []

        print("[Alipay] 输入 y 确认返回结果, 其他键放弃")
        try:
            confirm = input(">>> ").strip().lower()
            if confirm == "y":
                return valid
            else:
                print("[Alipay] 用户取消")
                return []
        except (EOFError, KeyboardInterrupt):
            print("[Alipay] 非交互模式, 放弃")
            return []

    # ==================== 屏幕尺寸 ====================

    def _get_screen_size(self) -> bool:
        try:
            import uiautomator2 as u2
            d = u2.connect(self.device_addr)
            try:
                w, h = d.window_size()
                print(f"[Alipay] uiautomator2 屏幕: {w}x{h}")
            except Exception:
                w, h = 0, 0

            if h < 500 or w < 300:
                out = self._adb_shell("wm size")
                m = re.search(r'(\d+)\s*x\s*(\d+)', out)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    print(f"[Alipay] adb wm size 屏幕: {w}x{h}")

            if h < 500:
                print(f"[Alipay] 屏幕高度 {h} < 500, 异常!")
                return False

            self.screen_w, self.screen_h = w, h
            return True
        except Exception as e:
            print(f"[Alipay] 获取屏幕尺寸失败: {e}")
            return False

    # ==================== 连接 ====================

    def _connect_emulator(self) -> bool:
        adb = self._find_adb()
        if not adb:
            return False
        self.adb_path = adb
        port = Config.LDPLAYER_ADB_PORT
        addr = f"127.0.0.1:{port}"
        self.device_addr = addr
        print(f"[Alipay] ADB: {adb}")
        r = subprocess.run([adb, "connect", addr],
                           capture_output=True, text=True, timeout=10)
        print(f"[Alipay] {r.stdout.strip()}")
        r = subprocess.run([adb, "-s", addr, "shell", "echo", "ok"],
                           capture_output=True, text=True, timeout=5)
        if "ok" not in r.stdout:
            return False
        r = subprocess.run([adb, "-s", addr, "shell", "pm", "list", "packages", ALIPAY_PACKAGE],
                           capture_output=True, text=True, timeout=5)
        return ALIPAY_PACKAGE in r.stdout

    def _find_adb(self) -> Optional[str]:
        if Config.LDPLAYER_PATH:
            p = os.path.join(Config.LDPLAYER_PATH, "adb.exe")
            if os.path.exists(p):
                return p
        for base in self.LDPLAYER_SEARCH_PATHS:
            p = os.path.join(base, "adb.exe")
            if os.path.exists(p):
                return p
        try:
            r = subprocess.run(["where", "adb"], capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                return r.stdout.strip().split("\n")[0].strip()
        except Exception:
            pass
        return None

    def _adb_shell(self, cmd: str) -> str:
        try:
            r = subprocess.run(
                [self.adb_path, "-s", self.device_addr, "shell"] + cmd.split(),
                capture_output=True, text=True, timeout=10)
            return r.stdout
        except Exception:
            return ""

    # ==================== uiautomator2 ====================

    def _u2_ensure_initialized(self, d) -> None:
        try:
            d.info
        except Exception:
            print("[Alipay] 初始化 uiautomator2 agent ...")
            r = subprocess.run(
                ["python", "-m", "uiautomator2", "init", "--addr", self.device_addr],
                capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                raise RuntimeError(f"uiautomator2 init 失败: {r.stderr}")
            time.sleep(3)

    # ==================== 导航 ====================

    def _u2_navigate_to_holdings(self, d) -> bool:
        print("[Alipay] 导航到基金持仓页面...")

        self._u2_click_tab(d, "理财")
        time.sleep(2.5)

        self._u2_click_tab(d, "基金")
        time.sleep(2.5)

        for attempt in range(5):
            if attempt > 0:
                print(f"[Alipay] 重试点击「持有」({attempt + 1}/5)...")
                time.sleep(1.5)

            self._u2_click_tab(d, "持有")
            time.sleep(2.5)

            if self._verify_holdings_page(d):
                print("[Alipay] 持有页面验证通过")
                return True

            print(f"[Alipay] 持有页面验证失败 (尝试 {attempt + 1}/5), 可能在其他页面")

        print("[Alipay] 多次尝试后仍未进入持有页面")
        return False

    def _u2_click_tab(self, d, text: str) -> None:
        try:
            el = d(text=text)
            if el.exists(timeout=4):
                el.click()
                print(f"[Alipay] 点击: {text}")
                return
        except Exception:
            pass

        try:
            el = d(textContains=text)
            if el.exists(timeout=3):
                el.click()
                print(f"[Alipay] 点击(textContains): {text}")
                return
        except Exception:
            pass

        try:
            el = d(description=text)
            if el.exists(timeout=3):
                el.click()
                print(f"[Alipay] 点击(description): {text}")
                return
        except Exception:
            pass

        print(f"[Alipay] 未找到可点击元素: {text}")

    def _verify_holdings_page(self, d) -> bool:
        try:
            xml = d.dump_hierarchy()
            texts = set(re.findall(r'(?:text|content-desc)="([^"]*)"', xml))
            found = [m for m in HOLDINGS_PAGE_MARKERS if m in texts]
            has_wode = "我的持有" in texts
            print(f"[Alipay] 页面检查: 我的持有={'有' if has_wode else '无'}, "
                  f"命中标记: {found}")
            if len(found) >= 2:
                return True
            return False
        except Exception as e:
            print(f"[Alipay] 页面检查异常: {e}")
            return False

    # ==================== 持有页解析 ====================

    # 版式常量 (原始坐标系, 截图为 1080x1920)
    CROP_TOP = 360
    CROP_BOTTOM = 1800
    COL_NAME_LEFT = 30
    COL_NAME_RIGHT = 620
    COL_AMT_LEFT = 650
    COL_AMT_RIGHT = 880
    COL_PROFIT_LEFT = 880
    COL_PROFIT_RIGHT = 1070
    OCR_SCALE = 2
    ROW_TOLERANCE = 80

    def _preprocess_holdings_image(self, image_path: str):
        """裁剪 + 放大 + 灰度化 + 增强对比度, 返回处理后的PIL Image"""
        try:
            from PIL import Image, ImageEnhance
        except ImportError:
            raise ImportError("pip install Pillow")

        img = Image.open(image_path)
        w, h = img.size
        print(f"[Alipay] 原图尺寸: {w}x{h}")

        crop_top = min(self.CROP_TOP, h)
        crop_bottom = min(self.CROP_BOTTOM, h)
        cropped = img.crop((0, crop_top, w, crop_bottom))
        print(f"[Alipay] 裁剪: y={crop_top}~{crop_bottom}, 尺寸={cropped.size}")

        new_w = cropped.width * self.OCR_SCALE
        new_h = cropped.height * self.OCR_SCALE
        scaled = cropped.resize((new_w, new_h), Image.LANCZOS)
        print(f"[Alipay] 放大 {self.OCR_SCALE}x: {scaled.size}")

        gray = scaled.convert("L")
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        print(f"[Alipay] 灰度+增强对比度完成")

        return enhanced, cropped, scaled

    def _parse_holdings_with_ocr_data(self, image_path: str):
        """
        卡片区间法解析基金持有页:
        1. 按列分离OCR块
        2. 找有效基金名 anchor (过滤财富号/广告行)
        3. 以每个anchor定义card区间, 在区间内匹配金额和收益
        4. 去重 (同金额只保留有效基金名)
        5. 模糊匹配修正
        """
        try:
            import pytesseract
        except ImportError:
            raise ImportError("pip install pytesseract")

        enhanced, cropped, scaled = self._preprocess_holdings_image(image_path)

        data = pytesseract.image_to_data(
            enhanced, lang="chi_sim+eng",
            output_type=pytesseract.Output.DICT
        )

        ocr_blocks = []
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text:
                continue
            conf = int(data["conf"][i])
            if conf < 0:
                continue
            left_s = data["left"][i]
            top_s = data["top"][i]
            w_s = data["width"][i]
            h_s = data["height"][i]

            orig_left = left_s / self.OCR_SCALE
            orig_top = top_s / self.OCR_SCALE + self.CROP_TOP
            orig_w = w_s / self.OCR_SCALE
            orig_h = h_s / self.OCR_SCALE

            ocr_blocks.append({
                "text": text,
                "left": left_s, "top": top_s,
                "width": w_s, "height": h_s,
                "orig_left": round(orig_left, 1),
                "orig_top": round(orig_top, 1),
                "orig_w": round(orig_w, 1),
                "orig_h": round(orig_h, 1),
                "conf": conf,
            })

        print(f"[Alipay] OCR 检测到 {len(ocr_blocks)} 个文本块 (conf>=0)")

        ocr_blocks.sort(key=lambda b: (b["orig_top"], b["orig_left"]))

        name_blocks = [b for b in ocr_blocks
                       if b["orig_left"] < self.COL_NAME_RIGHT
                       and not self._contains_wealth(b["text"])
                       and b["text"] not in BLOCKED_NAMES
                       and not re.match(r'^[\d\s\.\-\/:,¥￥%\+@]+$', b["text"])]

        amt_blocks = [b for b in ocr_blocks
                      if self.COL_AMT_LEFT <= b["orig_left"] <= self.COL_AMT_RIGHT]

        profit_blocks = [b for b in ocr_blocks
                         if b["orig_left"] > self.COL_AMT_RIGHT]

        print(f"[Alipay] 列分离: 名称候选={len(name_blocks)} 金额块={len(amt_blocks)} 收益块={len(profit_blocks)}")

        # 合并相邻名称块 (< 30px → 同名称行)
        merged_names = []
        used = set()
        for i, block in enumerate(name_blocks):
            if i in used:
                continue
            group = [block]
            group_y = block["orig_top"]
            for j in range(i + 1, len(name_blocks)):
                if j in used:
                    continue
                nb = name_blocks[j]
                if abs(nb["orig_top"] - group_y) <= 30:
                    group.append(nb)
                    used.add(j)
                else:
                    break
            used.add(i)
            group.sort(key=lambda b: (b["orig_top"], b["orig_left"]))
            ocr_name = "".join(b["text"] for b in group).strip()
            avg_y = sum(b["orig_top"] for b in group) / len(group)
            merged_names.append({"ocr_name": ocr_name, "y": avg_y, "blocks": group})

        # 过滤: 只保留模糊匹配到 KNOWN_FUNDS 的行作为 anchor
        fund_anchors = []
        for mn in merged_names:
            ocr_name = mn["ocr_name"]
            if self._is_noise(ocr_name):
                continue
            if self._contains_wealth(ocr_name):
                print(f"[Alipay] 丢弃广告/财富号: '{ocr_name[:28]}'")
                continue
            matched_name, match_score = self._fuzzy_match_fund_name(ocr_name)
            if matched_name and match_score >= 0.55:
                fund_anchors.append({
                    "fund_name": matched_name, "ocr_name": ocr_name,
                    "y": mn["y"], "blocks": mn["blocks"],
                    "match_score": match_score,
                })
                print(f"[Alipay] 基金 anchor: '{ocr_name[:28]}' -> '{matched_name}' (score={match_score:.2f})")
            else:
                if self._is_valid_fund_name(ocr_name):
                    print(f"[Alipay] 跳过(未匹配KNOWN_FUNDS): '{ocr_name[:28]}' score={match_score:.2f}")
                else:
                    print(f"[Alipay] 丢弃非基金: '{ocr_name[:28]}'")

        print(f"[Alipay] 基金 anchor ({len(fund_anchors)}): {[a['fund_name'][:16] for a in fund_anchors]}")

        if not fund_anchors:
            return [], ocr_blocks, scaled

        # 去重 anchor: 同一 KNOWN_FUNDS 去重
        seen_funds = set()
        unique_anchors = []
        for a in fund_anchors:
            if a["fund_name"] not in seen_funds:
                seen_funds.add(a["fund_name"])
                unique_anchors.append(a)
        fund_anchors = unique_anchors

        # 窗口搜索匹配 (anchor-centric, 不跨卡)
        fund_anchors.sort(key=lambda a: a["y"])

        # 也把右侧 x>700 的 amt_blocks 作为收益候选 (OCR 可能把收益放到金额列)
        amt_right_blocks = [b for b in amt_blocks
                            if b["orig_left"] > self.COL_AMT_LEFT + 50
                            and (re.search(r'[+\-]', b["text"]) or "%" in b["text"])]
        all_profit = profit_blocks + amt_right_blocks

        holdings = []
        for idx, anchor in enumerate(fund_anchors):
            y_center = anchor["y"]
            window_top = y_center - 80
            window_bottom = y_center + 120

            if idx + 1 < len(fund_anchors):
                next_y = fund_anchors[idx + 1]["y"]
                window_bottom = min(window_bottom, next_y - 30)

            card_name = anchor["fund_name"]
            print(f"[Alipay] 窗口 #{idx+1}: y={window_top:.0f}-{window_bottom:.0f} "
                  f"(center={y_center:.0f}) '{card_name}'")

            # 金额: x=650~880, 窗口内 >10 的数字, 取最接近 y_center 的
            win_amts = [(b, self._extract_number_from_block(b))
                        for b in amt_blocks
                        if window_top <= b["orig_top"] <= window_bottom]
            win_amts = [(b, v) for b, v in win_amts if v is not None and v > 10]
            if not win_amts:
                print(f"[Alipay] WARNING: {card_name} 金额缺失")
                continue
            win_amts.sort(key=lambda x: abs(x[0]["orig_top"] - y_center))
            amt_block, current_value = win_amts[0]

            # 收益: x>880 (或右侧 amt), 窗口内
            win_profits = [b for b in all_profit
                           if window_top <= b["orig_top"] <= window_bottom]

            profit_amount = None
            profit_rate = None
            pa_block, pa_dist = None, None
            pr_block, pr_dist = None, None

            signed_candidates = [b for b in win_profits
                                 if "%" not in b["text"]
                                 and re.search(r'[+\-]\d', b["text"])]
            if signed_candidates:
                best = min(signed_candidates,
                          key=lambda b: abs(b["orig_top"] - y_center))
                v = self._extract_signed_number(best["text"])
                if v is not None:
                    profit_amount = v
                    pa_block = best
                    pa_dist = abs(best["orig_top"] - y_center)

            pct_candidates = [b for b in win_profits
                              if "%" in b["text"]
                              and re.search(r'[+\-]?\s*\d', b["text"])]
            if pct_candidates:
                best = min(pct_candidates,
                          key=lambda b: abs(b["orig_top"] - y_center))
                v = self._extract_percentage(best["text"])
                if v is not None and -1.0 <= v <= 1.0:
                    profit_rate = v
                    pr_block = best
                    pr_dist = abs(best["orig_top"] - y_center)

            if profit_amount is None and profit_rate is None:
                print(f"[Alipay] WARNING: {card_name} 收益缺失 "
                      f"(窗口内 {len(win_profits)} 个收益块)")

            holdings.append({
                "fund_code": "",
                "fund_name": anchor["fund_name"],
                "ocr_name": anchor["ocr_name"],
                "current_value": round(current_value, 2),
                "profit_amount": round(profit_amount, 2) if profit_amount is not None else None,
                "profit_rate": round(profit_rate, 4) if profit_rate is not None else None,
                "shares": 0.0,
                "cost_amount": 0.0, "avg_cost": 0.0,
                "current_nav": 0.0, "market_value": round(current_value, 2),
                "daily_profit": 0.0,
                "total_profit": round(profit_amount, 2) if profit_amount is not None else 0,
                "total_profit_rate": round(profit_rate, 4) if profit_rate is not None else 0,
                "_debug": {
                    "name_y": round(y_center, 1),
                    "window_top": round(window_top, 1),
                    "window_bottom": round(window_bottom, 1),
                    "amount_y": round(amt_block["orig_top"], 1),
                    "amount_dist": round(abs(amt_block["orig_top"] - y_center), 1),
                    "profit_amt_y": round(pa_block["orig_top"], 1) if pa_block else None,
                    "profit_amt_dist": round(pa_dist, 1) if pa_block else None,
                    "profit_rate_y": round(pr_block["orig_top"], 1) if pr_block else None,
                    "profit_rate_dist": round(pr_dist, 1) if pr_block else None,
                    "match_score": round(anchor["match_score"], 3) if anchor.get("match_score") else None,
                },
            })

        # 去重: 同金额保留有效基金名
        holdings = self._deduplicate_holdings(holdings)

        print(f"[Alipay] 窗口匹配完成: {len(holdings)} 只基金 (去重后)")
        return holdings, ocr_blocks, scaled

    def _deduplicate_holdings(self, holdings: List[dict]) -> List[dict]:
        """同一 current_value 出现多条时, 保留有效基金名, 删除财富号/无效行"""
        seen = {}
        for h in holdings:
            cv = h["current_value"]
            name = h["fund_name"]
            if cv not in seen:
                seen[cv] = h
            else:
                existing = seen[cv]
                ex_valid = self._is_valid_fund_name(existing["fund_name"])
                new_valid = self._is_valid_fund_name(name)
                ex_matched = existing.get("_debug", {}).get("match_score") is not None
                new_matched = h.get("_debug", {}).get("match_score") is not None
                if new_valid and not ex_valid:
                    seen[cv] = h
                elif new_matched and not ex_matched:
                    seen[cv] = h
                elif new_valid and new_matched and not ex_matched:
                    seen[cv] = h
        if len(seen) < len(holdings):
            removed = len(holdings) - len(seen)
            print(f"[Alipay] 去重: 删除 {removed} 条重复/财富号记录")
        return list(seen.values())

    def _contains_wealth(self, text: str) -> bool:
        """检查文本是否包含财富号/广告关键词"""
        for kw in WEALTH_KEYWORDS:
            if kw in text:
                return True
        return False

    def _fuzzy_match_fund_name(self, ocr_name: str):
        """OCR文本与KNOWN_FUNDS模糊匹配, 返回 (matched_name, score) 或 (None, 0)"""
        if self._contains_wealth(ocr_name):
            return None, 0.0
        from difflib import SequenceMatcher
        best_name = None
        best_score = 0.0
        for known in KNOWN_FUNDS:
            score = SequenceMatcher(None, ocr_name, known).ratio()
            if score > best_score:
                best_score = score
                best_name = known
        if best_score >= 0.55:
            return best_name, best_score
        return None, 0.0

    def _extract_number_from_block(self, block: dict):
        """从OCR块提取正数金额"""
        text = block["text"].replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "")
        m = re.search(r'^(\d+\.?\d*)', text)
        if m:
            return float(m.group(1))
        return None

    def _extract_signed_number(self, text: str):
        """从文本提取带符号数字"""
        clean = text.replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "").replace("%", "")
        m = re.search(r'([+\-]\d+\.?\d*)', clean)
        if m:
            return float(m.group(1))
        return None

    def _extract_percentage(self, text: str):
        """从文本提取百分比, 返回小数"""
        clean = text.replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "")
        m = re.search(r'([+\-]?\d+\.?\d*)\s*%', clean)
        if m:
            val = float(m.group(1))
            if -100 <= val <= 100:
                return val / 100.0
        return None

    def _draw_debug_overlay(self, scaled_image, ocr_blocks: List[dict],
                            holdings: List[dict], output_path: str) -> None:
        """在放大后的截图上绘制 OCR 文本块和识别结果"""
        try:
            from PIL import ImageDraw, ImageFont, ImageColor
        except ImportError:
            print("[Alipay] 无法绘制 overlay (Pillow not available)")
            return

        img = scaled_image.convert("RGB")
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 14)
            font_sm = ImageFont.truetype("arial.ttf", 11)
        except Exception:
            font = ImageFont.load_default()
            font_sm = ImageFont.load_default()

        scale = self.OCR_SCALE

        for block in ocr_blocks:
            l, t, w, h = block["left"], block["top"], block["width"], block["height"]
            text = block["text"]
            x_orig = block["orig_left"]

            if x_orig < self.COL_NAME_RIGHT:
                color = (0, 180, 0)
            elif x_orig < self.COL_AMT_RIGHT:
                color = (0, 100, 255)
            else:
                color = (255, 60, 60)

            draw.rectangle([(l, t), (l + w, t + h)], outline=color, width=1)
            label = text[:12] + (".." if len(text) > 12 else "")
            draw.text((l + 2, t + h + 1), label, fill=color, font=font_sm)

        for x, label, color in [
            (self.COL_NAME_RIGHT * scale, "名称列", (0, 150, 0)),
            (self.COL_AMT_RIGHT * scale, "金额列", (0, 80, 200)),
            (self.COL_PROFIT_RIGHT * scale, "收益列", (200, 50, 50)),
        ]:
            draw.line([(x, 0), (x, img.height)], fill=color, width=1)
            draw.text((x + 3, 10), label, fill=color, font=font)

        for h in holdings:
            dbg = h.get("_debug", {})
            name_y = dbg.get("name_y")
            if name_y is not None:
                y_scaled = int((name_y - self.CROP_TOP) * scale)
                draw.line([(0, y_scaled), (img.width, y_scaled)],
                          fill=(255, 255, 0), width=2)
                info = f"{h['fund_name'][:16]} | {h['current_value']:.2f}"
                pr = h.get("profit_rate")
                if pr is not None:
                    info += f" | {pr*100:+.2f}%"
                draw.text((img.width - 350, y_scaled - 16),
                          info, fill=(255, 255, 0), font=font_sm)

        img.save(output_path)
        print(f"[Alipay] 调试 overlay 已保存: {output_path}")

    def _u2_extract_from_holdings_page(self, d) -> List[dict]:
        xml_path = os.path.join(DEBUG_DIR, "debug_hierarchy.xml")
        screenshot_path = os.path.join(DEBUG_DIR, "debug_screenshot.png")
        ocr_path = os.path.join(DEBUG_DIR, "debug_ocr.txt")
        ocr_tsv_path = os.path.join(DEBUG_DIR, "debug_ocr_tsv.txt")
        overlay_path = os.path.join(DEBUG_DIR, "debug_overlay.png")

        d.screenshot(screenshot_path)
        print(f"[Alipay] 已保存截图: {screenshot_path}")

        xml = d.dump_hierarchy()
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml)
        print(f"[Alipay] 已保存 XML: {xml_path} ({len(xml)} 字节)")

        holdings = []

        try:
            holdings, ocr_blocks, scaled = self._parse_holdings_with_ocr_data(screenshot_path)

            if ocr_blocks:
                with open(ocr_tsv_path, "w", encoding="utf-8") as f:
                    f.write("text\tleft\ttop\twidth\theight\torig_left\torig_top\tconf\n")
                    for b in ocr_blocks:
                        f.write(f"{b['text']}\t{b['left']}\t{b['top']}\t"
                                f"{b['width']}\t{b['height']}\t"
                                f"{b['orig_left']}\t{b['orig_top']}\t{b['conf']}\n")
                print(f"[Alipay] 已保存 OCR TSV: {ocr_tsv_path}")

            with open(ocr_path, "w", encoding="utf-8") as f:
                for b in ocr_blocks:
                    f.write(f"[{b['orig_left']:5.0f},{b['orig_top']:5.0f} c={b['conf']:3d}] {b['text']}\n")
            print(f"[Alipay] 已保存 OCR 文本: {ocr_path}")

            self._draw_debug_overlay(scaled, ocr_blocks, holdings, overlay_path)

        except ImportError as e:
            print(f"[Alipay] OCR 依赖缺失: {e}")
        except Exception as e:
            print(f"[Alipay] OCR 解析失败: {e}")
            import traceback
            traceback.print_exc()

        if not holdings:
            print("[Alipay] OCR 解析为空, 尝试 XML 兜底...")
            holdings = self._parse_holdings_from_xml(xml)

        return holdings

    # ==================== XML 兜底解析 ====================

    def _parse_holdings_from_xml(self, xml: str) -> List[dict]:
        if not xml:
            return []

        all_nodes = []
        for m in re.finditer(
            r'<(?:node|android\.[^>]*\b)(?:text|content-desc)="([^"]*)"[^>]*'
            r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"[^>]*>',
            xml
        ):
            text = m.group(1).strip()
            if not text:
                continue
            x1, y1, x2, y2 = int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
            all_nodes.append((text, x1, y1, x2, y2))

        if not all_nodes:
            return []

        top_y = 0
        for text, x1, y1, x2, y2 in all_nodes:
            if text == "我的持有":
                top_y = y1
                print(f"[Alipay] 找到「我的持有」Y={y1}")
                break

        if top_y == 0:
            return []

        bottom_y = max(n[4] for n in all_nodes)
        for text, x1, y1, x2, y2 in all_nodes:
            if text in BOTTOM_NAV_TEXTS and y1 > top_y + 200:
                if y1 < bottom_y:
                    bottom_y = y1

        print(f"[Alipay] XML 解析区域 Y: {top_y} ~ {bottom_y}")

        region_nodes = [
            (t, x1, y1, x2, y2) for t, x1, y1, x2, y2 in all_nodes
            if top_y - 30 <= y1 <= bottom_y
        ]
        region_nodes.sort(key=lambda n: (n[3], n[1]))

        rows = []
        current_row = []
        last_y = -999
        for node in region_nodes:
            _, _, _, y, _ = node
            if current_row and abs(y - last_y) > 60:
                rows.append(current_row)
                current_row = []
                last_y = y
            if not current_row:
                last_y = y
            current_row.append(node)
        if current_row:
            rows.append(current_row)

        print(f"[Alipay] XML 区域内共 {len(rows)} 行")

        holdings = []
        for row in rows:
            h = self._parse_fund_row(row)
            if h:
                holdings.append(h)

        return holdings

    def _parse_fund_row(self, row: List[Tuple]) -> Optional[dict]:
        if len(row) < 2:
            return None

        row.sort(key=lambda n: n[1])

        fund_name = ""
        for text, x1, y1, x2, y2 in row:
            if self._is_valid_fund_name(text):
                fund_name = text
                break

        if not fund_name:
            return None

        current_value = 0.0
        profit_amount = 0.0
        profit_rate = 0.0

        for text, x1, y1, x2, y2 in row:
            clean = text.replace(",", "").replace("¥", "").replace("￥", "").replace(" ", "")

            pct = re.search(r'([+-]?\d+\.?\d*)\s*%', clean)
            if pct:
                val = float(pct.group(1))
                if -100 <= val <= 100:
                    profit_rate = val / 100.0
                    continue

            signed = re.search(r'^([+-]\d+\.?\d*)', clean)
            if signed:
                val = float(signed.group(1))
                if -100000000 < val < 100000000:
                    profit_amount = val
                    continue

            num = re.search(r'^(\d+\.?\d*)', clean)
            if num:
                val = float(num.group(1))
                if 0.01 < val < 100000000:
                    if val > current_value:
                        current_value = val

        if current_value < 10:
            return None

        return {
            "fund_code": "",
            "fund_name": fund_name,
            "current_value": round(current_value, 2),
            "profit_amount": round(profit_amount, 2),
            "profit_rate": round(profit_rate, 4),
            "shares": 0.0, "cost_amount": 0.0, "avg_cost": 0.0,
            "current_nav": 0.0, "market_value": round(current_value, 2),
            "daily_profit": 0.0,
            "total_profit": round(profit_amount, 2),
            "total_profit_rate": round(profit_rate, 4),
        }

    # ==================== 验证 ====================

    def _is_valid_holding(self, h: dict) -> bool:
        name = h.get("fund_name", "")
        if not self._is_valid_fund_name(name):
            return False

        cv = h.get("current_value", 0)
        if not isinstance(cv, (int, float)) or cv < 10:
            return False

        pr = h.get("profit_rate")
        if pr is not None and (pr < -1.0 or pr > 1.0):
            return False

        return True

    def _is_valid_fund_name(self, name: str) -> bool:
        if not name:
            return False
        name = name.strip()
        if len(name) < 5:
            return False
        if name in BLOCKED_NAMES:
            return False
        if self._contains_wealth(name):
            return False
        if self._is_noise(name):
            return False
        if not any(kw in name for kw in FUND_NAME_KEYWORDS):
            return False
        return True

    def _is_noise(self, text: str) -> bool:
        if not text or len(text) < 2:
            return True
        for p in NOISE_PATTERNS:
            if p in text:
                return True
        if re.match(r'^[\d\s\.\-\/:,¥￥%\+]+$', text):
            return True
        return False

    # ==================== OCR ====================

    def _ocr_screenshot_raw(self, image_path: str) -> str:
        try:
            from PIL import Image
            import pytesseract
            return pytesseract.image_to_string(Image.open(image_path), lang="chi_sim+eng")
        except ImportError:
            return ""
        except Exception as e:
            print(f"[Alipay] OCR失败: {e}")
            return ""

    # ==================== 手动录入 ====================

    def manual_input_holdings(self) -> List[dict]:
        print("\n" + "=" * 50)
        print("  手动录入基金持仓")
        print("  支付宝 -> 理财 -> 基金 -> 持有")
        print("  点击每只基金查看详情, 录入:")
        print("    基金代码 | 名称 | 份额 | 本金")
        print("  输入 q 结束当前字段录入")
        print("=" * 50 + "\n")
        holdings = []
        idx = 1
        while True:
            print(f"--- 第 {idx} 只 ---")
            code = input("  代码: ").strip()
            if code.lower() == "q":
                print("  结束录入")
                break

            name = input("  名称: ").strip()
            if not name or name.lower() == "q":
                print("  结束录入")
                break

            shares_input = input("  份额: ").strip()
            if shares_input.lower() == "q":
                print("  结束录入")
                break
            try:
                shares = float(shares_input) if shares_input else 0
            except ValueError:
                print("  无效数字, 跳过")
                continue

            cost_input = input("  本金: ").strip()
            if cost_input.lower() == "q":
                print("  结束录入")
                break
            try:
                cost = float(cost_input) if cost_input else 0
            except ValueError:
                print("  无效数字, 跳过")
                continue

            avg = cost / shares if shares > 0 else 0
            holdings.append({
                "fund_code": code if (code.isdigit() and len(code) == 6) else "",
                "fund_name": name,
                "shares": shares,
                "cost_amount": cost,
                "avg_cost": avg,
                "current_nav": 0,
                "market_value": cost,
                "current_value": cost,
                "profit_amount": 0,
                "profit_rate": 0,
                "daily_profit": 0,
                "total_profit": 0,
                "total_profit_rate": 0,
            })
            print(f"  OK: {name}\n")
            idx += 1

        print(f"[Alipay] 手动录入共 {len(holdings)} 只")
        return holdings

    # ==================== 测试函数 ====================

    def test_parse_current_screen(self) -> List[dict]:
        """只解析当前模拟器画面, 不导航, 不写入数据库"""
        print("\n" + "=" * 60)
        print("[Test] 解析当前画面 (不导航, 不写入DB)")
        print("=" * 60)

        if not self._connect_emulator():
            print("[Test] 无法连接模拟器")
            return []

        if not self._get_screen_size():
            print("[Test] 屏幕尺寸异常")
            return []

        try:
            import uiautomator2 as u2
            d = u2.connect(self.device_addr)
            self._u2_ensure_initialized(d)
        except Exception as e:
            print(f"[Test] uiautomator2 失败: {e}")
            return []

        xml_path = os.path.join(DEBUG_DIR, "debug_hierarchy.xml")
        screenshot_path = os.path.join(DEBUG_DIR, "debug_screenshot.png")
        ocr_path = os.path.join(DEBUG_DIR, "debug_ocr.txt")
        ocr_tsv_path = os.path.join(DEBUG_DIR, "debug_ocr_tsv.txt")
        overlay_path = os.path.join(DEBUG_DIR, "debug_overlay.png")

        xml = d.dump_hierarchy()
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml)
        print(f"[Test] XML: {xml_path} ({len(xml)} 字节)")

        d.screenshot(screenshot_path)
        print(f"[Test] 截图: {screenshot_path}")

        holdings = []
        ocr_blocks = []

        try:
            holdings, ocr_blocks, scaled = self._parse_holdings_with_ocr_data(screenshot_path)

            if ocr_blocks:
                with open(ocr_tsv_path, "w", encoding="utf-8") as f:
                    f.write("text\tleft\ttop\twidth\theight\torig_left\torig_top\tconf\n")
                    for b in ocr_blocks:
                        f.write(f"{b['text']}\t{b['left']}\t{b['top']}\t"
                                f"{b['width']}\t{b['height']}\t"
                                f"{b['orig_left']}\t{b['orig_top']}\t{b['conf']}\n")
                print(f"[Test] OCR TSV: {ocr_tsv_path}")

            with open(ocr_path, "w", encoding="utf-8") as f:
                for b in ocr_blocks:
                    f.write(f"[{b['orig_left']:5.0f},{b['orig_top']:5.0f} "
                            f"c={b['conf']:3d}] {b['text']}\n")
            print(f"[Test] OCR 文本: {ocr_path}")

            self._draw_debug_overlay(scaled, ocr_blocks, holdings, overlay_path)

        except ImportError as e:
            print(f"[Test] OCR 依赖缺失: {e}")
        except Exception as e:
            print(f"[Test] OCR 解析失败: {e}")
            import traceback
            traceback.print_exc()

        valid = [h for h in holdings if self._is_valid_holding(h)]
        complete = [h for h in valid
                    if h.get("profit_amount") is not None
                    and h.get("profit_rate") is not None]

        print(f"\n[Test] ====== 解析结果 ({len(valid)} 只有效, {len(complete)} 只完整) ======")
        print(f"{'#':>2s} {'OCR原始名称':30s} | {'修正名称':30s} | "
              f"{'金额':>10s} | {'收益':>10s} | {'收益率':>8s}")
        print("-" * 120)
        for i, h in enumerate(valid, 1):
            ocr_name = h.get("ocr_name", h["fund_name"])[:28]
            fund_name = h["fund_name"][:28]
            cv = h.get("current_value", 0)
            pa = h.get("profit_amount")
            pr = h.get("profit_rate")
            pa_str = f"{pa:+.2f}" if pa is not None else "  None  "
            pr_str = f"{pr*100:+.2f}%" if pr is not None else "  None  "

            marker = " " if h in complete else "!"
            print(f"{marker}{i:1d} {ocr_name:30s} | {fund_name:30s} | "
                  f"{cv:10.2f} | {pa_str:>10s} | {pr_str:>8s}")

        print("-" * 120)
        print(f"{'#':>2s} {'OCR原始名称':30s} | {'Y_name':>6s} | {'Y_amt':>6s} | "
              f"{'d_amt':>5s} | {'Y_prof':>6s} | {'d_prof':>5s} | {'Y_rate':>6s} | "
              f"{'d_rate':>5s} | {'match':>5s}")
        print("-" * 90)
        for i, h in enumerate(valid, 1):
            dbg = h.get("_debug", {})
            name_y = dbg.get("name_y", 0)
            amt_y = dbg.get("amount_y", 0)
            amt_d = dbg.get("amount_dist", 0)
            prof_y = dbg.get("profit_amt_y") or 0
            prof_d = dbg.get("profit_amt_dist") or 0
            rate_y = dbg.get("profit_rate_y") or 0
            rate_d = dbg.get("profit_rate_dist") or 0
            score = dbg.get("match_score") or 0
            ocr_name = h.get("ocr_name", h["fund_name"])[:28]
            print(f"{i:2d} {ocr_name:30s} | {name_y:6.0f} | {amt_y:6.0f} | "
                  f"{amt_d:5.0f} | {prof_y:6.0f} | {prof_d:5.0f} | "
                  f"{rate_y:6.0f} | {rate_d:5.0f} | {score:5.2f}")

        if not valid:
            print("  (无有效基金)")
        print("[Test] ====== 结果结束 ======\n")

        # 安全检查
        missing_profit = [h for h in valid if h.get("profit_amount") is None or h.get("profit_rate") is None]
        if missing_profit:
            print(f"[Test] WARNING: {len(missing_profit)} 只基金收益缺失, 不会自动写入数据库")
        if len(valid) < 6:
            print(f"[Test] WARNING: 仅识别 {len(valid)} 只 (<6), 可能存在遗漏, 不会自动写入数据库")

        print(f"[Test] 调试文件: {screenshot_path}")
        print(f"[Test] 调试文件: {ocr_tsv_path}")
        print(f"[Test] 调试文件: {overlay_path}")
        print("[Test] 未写入数据库。")

        return valid


def test_parse_current_screen():
    """CLI入口: 只解析当前画面, 不做任何导航"""
    scraper = AlipayScraper()
    return scraper.test_parse_current_screen()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_parse_current_screen()
    else:
        scraper = AlipayScraper()
        holdings = scraper.fetch_holdings()
        print(f"\n最终结果: {len(holdings)} 只基金")
        print(json.dumps(holdings, ensure_ascii=False, indent=2))
