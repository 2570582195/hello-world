#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
BTC + ETH 实时监控脚本 v5（干净版 · 动态关键位）
- Gate.io API 无缓存实时数据（30秒检查）
- BTC价格变动≥0.3%、ETH≥0.2%立刻推企微
- 触及关键位（容差0.3%）立刻推企微 + 实时数据
- 启动时推送通知（含当前价格+关键位列表）
- 防掉线：失败重试 + 守护进程自动重启
- 关键位从 market_data.json 动态读取，读取失败用兜底硬编码
"""

import requests
import time
import os
import sys
import json
import re
from datetime import datetime

# ============ 配置区 ============
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"

# ★ 自动检测运行目录（Windows/Linux通用）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 关键位字典（在 main() 里由 get_key_levels() 动态填充）
BTC_LEVELS = {}
ETH_LEVELS = {}

# 价格变动阈值
BTC_CHANGE_THRESHOLD = 0.003   # 0.3%
ETH_CHANGE_THRESHOLD = 0.002   # 0.2%
LEVEL_TOLERANCE_PCT   = 0.003  # 关键位容差 0.3%

CHECK_INTERVAL     = 30     # 价格检查间隔（秒）
MAX_FAILS_BEFORE_EXIT = 5
HEARTBEAT_FILE     = os.path.join(BASE_DIR, "monitor_v5.heartbeat")
MARKET_DATA_FILE   = os.path.join(BASE_DIR, "market_data.json")
LOG_FILE           = os.path.join(BASE_DIR, "monitor_v5.log")
FAIL_LOG           = os.path.join(BASE_DIR, "monitor_v5_fail.log")

HEADERS = {
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache',
    'Expires': '0',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def send_wechat(msg):
    """发送企微消息"""
    try:
        payload = {"msgtype": "text", "text": {"content": msg}}
        resp = requests.post(WECHAT_WEBHOOK, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print(f"  ✅ 企微推送成功")
            return True
        else:
            print(f"  ❌ 企微推送失败: {result}")
    except Exception as e:
        print(f"  ❌ 企微推送异常: {e}")
    try:
        with open(FAIL_LOG, "a") as f:
            f.write(f"[{datetime.now()}] PUSH_FAIL: {msg[:100]}\n")
    except:
        pass
    return False


def update_heartbeat():
    """更新心跳文件"""
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(f"{datetime.now()}")
    except:
        pass


# ==================== 动态关键位（实时计算 + 自检）====================
import importlib.util

# 加载实时分析模块（同目录下的 realtime_analysis.py）
def _load_realtime_module():
    """加载 realtime_analysis.py 模块"""
    module_path = os.path.join(BASE_DIR, "realtime_analysis.py")
    if not os.path.exists(module_path):
        return None
    spec = importlib.util.spec_from_file_location("realtime_analysis", module_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"  ⚠️ 实时分析模块加载失败: {e}")
        return None

_rt_module = None  # 延迟加载

# 缓存：避免每次都调API（缓存5分钟)
_level_cache = {'BTC': (None, 0), 'ETH': (None, 0)}  # (result_dict, timestamp)


def get_key_levels(symbol="BTC"):
    """
    ★ 从 Gate.io API 实时获取 K线 → 计算真实关键位
    数据来源优先级：
      1. realtime_analysis.py（实时K线 + Pivot + Fib + MA + BB + 心理位 + 自检）
      2. market_data.json（离线缓存/TV快照，仅作备用）
      3. 硬编码兜底（标注"假数据"，仅最后防线）

    返回 {price_float: "名称"} 字典
    铁律：支撑 < 当前价格 < 阻力
    """
    global _rt_module

    now = time.time()
    cached_result, cached_ts = _level_cache.get(symbol, (None, 0))

    # 缓存有效期内直接返回（5分钟）
    if cached_result and (now - cached_ts) < 300:
        return cached_result

    result = {}

    # ── 方式一：实时分析模块（★ 首选）──
    if _rt_module is None:
        _rt_module = _load_realtime_module()

    if _rt_module:
        try:
            analysis = _rt_module.analyze_symbol(symbol)
            if 'error' not in analysis and 'key_levels' in analysis:
                kl = analysis['key_levels']
                # 合并支撑+阻力到一个字典
                for p, n in kl.get('supports', {}).items():
                    result[p] = f"🔽{n}"
                for p, n in kl.get('resistances', {}).items():
                    result[p] = f"🔼{n}"

                sc = analysis.get('self_check', {})
                status = '✅' if sc.get('passed') else '⚠️'
                price = analysis.get('price', 0)

                print(f"  📊 [{status}] 实时分析: BTC ${price:,.0f}" if symbol == 'BTC'
                      else f"  📊 [{status}] 实时分析: ETH ${price:,.2f}")
                print(f"     支撑{kl.get('support_count',0)}个 + 阻力{kl.get('resistance_count',0)}个 | "
                      f"铁律:{'通过' if sc.get('passed') else '失败'}")

                # 更新缓存
                _level_cache[symbol] = (result, now)

                # 同时更新market_data.json供其他脚本用
                _update_market_cache(symbol, analysis)

                return result
        except Exception as e:
            print(f"  ⚠️ 实时分析执行失败: {e}")

    # ── 方式二：从 market_data.json 读取（备用）──
    data = _load_market_data()
    tv_key = f"tv_{symbol.lower()}"
    tv_data = data.get(tv_key, {})
    if tv_data:
        pivot_map = {
            "S3": "S3强支撑", "S2": "S2支撑", "S1": "S1支撑",
            "Pivot": "中枢Pivot",
            "R1": "R1压力",   "R2": "R2强压",
        }
        for field, name in pivot_map.items():
            val = tv_data.get(field)
            if val is not None and isinstance(val, (int, float)) and val > 0:
                result[float(val)] = name
        if result:
            print(f"  📊 [备用] 从{tv_key}提取到 {len(result)}个关键位")
            _level_cache[symbol] = (result, now)
            return result

    # ── 兜底：硬编码（标注假数据）──
    if symbol == "BTC":
        result = {
            57000: "🔽心理$57k(假)",  58000: "🔽心理$58k(假)",
            59000: "🔽心理$59k(假)",  60000: "🔼心理$60k(假)",
            61000: "🔼心理$61k(假)",  62000: "🔼心理$62k(假)",
        }
    else:
        result = {
            1450: "🔽心理$1450(假)", 1500: "🔽心理$1500(假)",
            1550: "🔽心理$1550(假)", 1600: "🔼心理$1600(假)",
            1650: "🔼心理$1650(假)", 1700: "🔼心理$1700(假)",
        }
    print(f"  ⚠️ 使用硬编码兜底关键位({len(result)}个) — 无实时数据！")
    _level_cache[symbol] = (result, now)
    return result


def _update_market_cache(symbol, analysis):
    """将实时分析结果写回 market_data.json（供 push_ultimate_v4_fixed.py 使用）"""
    try:
        with open(MARKET_DATA_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}

    key = f"rt_{symbol.lower()}"
    cache[key] = {
        'price': analysis.get('price'),
        'key_levels': analysis.get('key_levels'),
        'indicators': analysis.get('indicators'),
        'pivots': analysis.get('pivots'),
        'self_check': analysis.get('self_check'),
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    try:
        with open(MARKET_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ==================== 原有函数 ====================
def get_price(contract, retry=3):
    """
    获取实时价格（优先Binance，兜底Gate.io）
    contract: "BTC_USDT" 或 "ETH_USDT"
    返回: float价格 或 None
    """
    # 转换合约名到Binance格式
    symbol_map = {
        "BTC_USDT": "BTCUSDT",
        "ETH_USDT": "ETHUSDT"
    }
    binance_symbol = symbol_map.get(contract, contract.replace("_", ""))

    # 方法1: Binance公开API（无需API Key）
    for i in range(retry):
        try:
            resp = requests.get(
                f'https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}',
                headers=HEADERS, timeout=10)
            data = resp.json()
            if 'price' in data:
                price = float(data['price'])
                print(f"  ✅ Binance {binance_symbol}: ${price}")
                return price
        except Exception as e:
            print(f"  ⚠️ Binance {binance_symbol} 第{i+1}次失败: {type(e).__name__}")
            if i < retry - 1:
                time.sleep(2)

    # 方法2: Gate.io兜底
    print(f"  ⚠️ Binance失败，尝试Gate.io: {contract}")
    for i in range(retry):
        try:
            resp = requests.get(
                f'https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={contract}',
                headers=HEADERS, timeout=10)
            data = resp.json()
            if isinstance(data, list) and data:
                price = float(data[0]['last'])
                print(f"  ✅ Gate.io {contract}: ${price}")
                return price
        except Exception as e:
            print(f"  ⚠️ Gate.io {contract} 第{i+1}次失败: {type(e).__name__}")
            if i < retry - 1:
                time.sleep(2)

    return None


def get_gate_ticker(contract):
    """获取Gate.io完整ticker数据"""
    for i in range(3):
        try:
            resp = requests.get(
                f'https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={contract}',
                headers=HEADERS, timeout=10)
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0]
        except:
            time.sleep(3)
    return None


def main():
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("=" * 60)
    print("BTC + ETH 实时监控 v5 启动（动态关键位）")
    print(f"启动时间: {start_time}")
    print(f"检查间隔: {CHECK_INTERVAL}秒 | 无定时推送")
    print("=" * 60, flush=True)

    # ★ 立刻写心跳文件（让守护进程能马上检测到）
    update_heartbeat()
    print(f"  💓 心跳文件已写入: {HEARTBEAT_FILE}")

    # ★ 启动时动态加载关键位
    global BTC_LEVELS, ETH_LEVELS
    BTC_LEVELS = get_key_levels("BTC")
    ETH_LEVELS = get_key_levels("ETH")
    print(f"  📊 动态关键位已加载: BTC {len(BTC_LEVELS)}个, ETH {len(ETH_LEVELS)}个")

    # 启动通知（含当前价格+关键位列表）
    init_btc = get_price("BTC_USDT")
    init_eth = get_price("ETH_USDT")
    btc_levels_str = "、".join([f"${x}" for x in sorted(BTC_LEVELS.keys())])
    eth_levels_str = "、".join([f"${x}" for x in sorted(ETH_LEVELS.keys())])
    price_line = ""
    if init_btc and init_eth:
        price_line = f"\n💰 当前价: BTC ${init_btc:.1f} | ETH ${init_eth:.2f}"
    startup_msg = (
        f"🟢 监控系统 v5 已启动（动态关键位）\n"
        f"⏰ {start_time}{price_line}\n"
        f"{'─'*24}\n"
        f"📊 监控配置\n"
        f"• BTC变动阈值: 0.3%\n"
        f"• ETH变动阈值: 0.2%\n"
        f"• BTC关键位: {btc_levels_str}\n"
        f"• ETH关键位: {eth_levels_str}\n"
        f"• 定时推送: 无（仅价格变动+关键位警报）\n"
        f"⚠️ 有变动立刻通知"
    )
    send_wechat(startup_msg)

    # 从日志恢复基准价
    def load_last_push_price():
        try:
            if not os.path.exists(LOG_FILE):
                return None, None
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
                btc_p = None
                eth_p = None
                for line in reversed(lines):
                    line = line.strip()
                    if not line or line[0] != '[':
                        continue
                    if "BTC:" in line and "ETH:" in line:
                        m_btc = re.search(r"^\[.*?\]\s*BTC:\s*\$([0-9]+\.?[0-9]*)", line)
                        m_eth = re.search(r"ETH:\s*\$([0-9]+\.?[0-9]*)", line)
                        if m_btc:
                            val = float(m_btc.group(1))
                            if 50000 < val < 100000:
                                btc_p = val
                        if m_eth:
                            val = float(m_eth.group(1))
                            if 1000 < val < 10000:
                                eth_p = val
                    if btc_p and eth_p:
                        break
                if btc_p:
                    print(f"  📋 从日志恢复BTC基准价: ${btc_p:.1f}")
                if eth_p:
                    print(f"  📋 从日志恢复ETH基准价: ${eth_p:.2f}")
                return btc_p, eth_p
        except Exception as e:
            print(f"  ⚠️ 恢复基准价失败: {e}")
        return None, None

    alerted_btc = set()
    alerted_eth = set()
    last_btc = None
    last_eth = None
    last_btc_push = None
    last_eth_push = None
    fail_count = 0
    loop_count = 0
    last_heartbeat = 0

    restored_btc, restored_eth = load_last_push_price()
    if restored_btc:
        last_btc_push = restored_btc
    if restored_eth:
        last_eth_push = restored_eth

    while True:
        try:
            loop_count += 1
            now_ts = time.time()
            now = datetime.now().strftime('%H:%M:%S')

            # 每5分钟更新心跳
            if now_ts - last_heartbeat >= 300:
                update_heartbeat()
                last_heartbeat = now_ts

            # 获取实时价格
            btc = get_price("BTC_USDT")
            eth = get_price("ETH_USDT")

            if btc is None or eth is None:
                fail_count += 1
                print(f"[{now}] ⚠️ 获取价格失败({fail_count}/{MAX_FAILS_BEFORE_EXIT})")
                if fail_count >= MAX_FAILS_BEFORE_EXIT:
                    print(f"[{now}] ❌ 连续失败{MAX_FAILS_BEFORE_EXIT}次，exit(1)让守护脚本重启...")
                    send_wechat(f"🔄 监控脚本自动重启\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n原因: API连续失败{MAX_FAILS_BEFORE_EXIT}次")
                    time.sleep(2)
                    sys.exit(1)
                time.sleep(CHECK_INTERVAL)
                continue
            fail_count = 0

            # 初始化基准价
            if last_btc_push is None:
                last_btc_push = btc
            if last_eth_push is None:
                last_eth_push = eth

            # 日志
            btc_chg = ""
            eth_chg = ""
            if last_btc:
                btc_chg = f" ({(btc-last_btc)/last_btc*100:+.2f}%)"
            if last_eth:
                eth_chg = f" ({(eth-last_eth)/last_eth*100:+.2f}%)"
            log_line = f"[{now}] BTC: ${btc:.1f}{btc_chg} | ETH: ${eth:.2f}{eth_chg}"
            print(log_line, flush=True)
            try:
                with open(LOG_FILE, "a") as f:
                    f.write(log_line + "\n")
            except:
                pass

            # 价格变动推送（BTC 0.3%，ETH 0.2%）
            btc_pct = abs(btc - last_btc_push) / last_btc_push
            eth_pct = abs(eth - last_eth_push) / last_eth_push

            if btc_pct >= BTC_CHANGE_THRESHOLD:
                direction = "📈" if btc > last_btc_push else "📉"
                send_wechat(f"{direction} BTC 价格变动\n当前价：${btc:.1f}\n变动：{(btc-last_btc_push)/last_btc_push*100:+.2f}%\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                last_btc_push = btc
                alerted_btc.clear()

            if eth_pct >= ETH_CHANGE_THRESHOLD:
                direction = "📈" if eth > last_eth_push else "📉"
                send_wechat(f"{direction} ETH 价格变动\n当前价：${eth:.2f}\n变动：{(eth-last_eth_push)/last_eth_push*100:+.2f}%\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                last_eth_push = eth
                alerted_eth.clear()

            # 关键位检查（容差0.3%）
            for target, msg in BTC_LEVELS.items():
                if abs(btc - target) / target <= LEVEL_TOLERANCE_PCT:
                    key = f"btc_{target}"
                    if key not in alerted_btc:
                        send_wechat(f"【BTC关键位警报】\n{msg}\n\n当前价: ${btc:.1f}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        alerted_btc.add(key)

            for target, msg in ETH_LEVELS.items():
                if abs(eth - target) / target <= LEVEL_TOLERANCE_PCT:
                    key = f"eth_{target}"
                    if key not in alerted_eth:
                        send_wechat(f"【ETH关键位警报】\n{msg}\n\n当前价: ${eth:.2f}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        alerted_eth.add(key)

            # 10轮状态确认
            if loop_count % 20 == 0:
                print(f"  💤 监控正常，无警报（第{loop_count}轮）", flush=True)

            last_btc = btc
            last_eth = eth
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n⏹️ 监控已停止")
            break
        except Exception as e:
            print(f"❌ 未捕获错误: {e}", flush=True)
            time.sleep(10)


if __name__ == "__main__":
    main()
