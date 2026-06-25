#!/usr/bin/env python3.11
"""
BTC + ETH 实时监控脚本 v5（干净版）
- Gate.io API 无缓存实时数据（30秒检查）
- BTC价格变动≥0.3%、ETH≥0.2%立刻推企微
- 触及关键位（容差0.3%）立刻推企微 + 实时数据
- 启动时推送通知（含当前价格+关键位列表）
- 防掉线：失败重试 + 守护进程自动重启
- 无链上定时推送 / 无终极分析自动推送
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

# 关键位（TV Pivot Classic实时计算，需要定期手动更新）
# BTC: S2=59376, S1=60229, P=76346, R1=62568, R2=64054
# ETH: S2=1604,  S1=1625,  P=2133,  R1=1680, R2=1713
BTC_LEVELS = {
    58300: "🔴 BTC逼近S3 $58,300！破位看$55,000，极度危险",
    59376: "🔴 BTC触及S2强支撑 $59,376！超卖反弹窗口，严格止损",
    60229: "🟡 BTC触及S1支撑 $60,229！关注止跌信号",
    62568: "🟠 BTC触及R1压力 $62,568！短期可能受阻",
    64054: "🔴 BTC触及R2强压力 $64,054！做空机会",
}

ETH_LEVELS = {
    1580: "🔴 ETH逼近S3 $1,580！破位看$1,500，极度危险",
    1604: "🔴 ETH触及S2强支撑 $1,604！超卖，但破位风险高",
    1625: "🟡 ETH触及S1支撑 $1,625！关注止跌信号",
    1680: "🟠 ETH触及R1压力 $1,680！短期可能受阻",
    1713: "🔴 ETH触及R2强压力 $1,713！做空机会",
}

# 价格变动阈值
BTC_CHANGE_THRESHOLD = 0.003   # 0.3%
ETH_CHANGE_THRESHOLD = 0.002   # 0.2%
LEVEL_TOLERANCE_PCT   = 0.003  # 关键位容差 0.3%

CHECK_INTERVAL     = 30     # 价格检查间隔（秒）
MAX_FAILS_BEFORE_EXIT = 5
HEARTBEAT_FILE     = "/workspace/monitor_v5.heartbeat"
LOG_FILE           = "/workspace/monitor_v5.log"
FAIL_LOG           = "/workspace/monitor_v5_fail.log"

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


def get_price(contract, retry=3):
    """获取Gate.io期货实时价格，失败重试"""
    for i in range(retry):
        try:
            resp = requests.get(
                f'https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={contract}',
                headers=HEADERS, timeout=10)
            data = resp.json()
            if isinstance(data, list) and data:
                return float(data[0]['last'])
        except Exception as e:
            print(f"  ⚠️ Gate.io {contract} 第{i+1}次失败: {type(e).__name__}")
            if i < retry - 1:
                time.sleep(3)
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
    print("BTC + ETH 实时监控 v5 启动")
    print(f"启动时间: {start_time}")
    print(f"检查间隔: {CHECK_INTERVAL}秒 | 无定时推送")
    print("=" * 60, flush=True)

    # 启动通知（含当前价格+关键位列表）
    init_btc = get_price("BTC_USDT")
    init_eth = get_price("ETH_USDT")
    btc_levels_str = "、".join([f"${x}" for x in sorted(BTC_LEVELS.keys())])
    eth_levels_str = "、".join([f"${x}" for x in sorted(ETH_LEVELS.keys())])
    price_line = ""
    if init_btc and init_eth:
        price_line = f"\n💰 当前价: BTC ${init_btc:.1f} | ETH ${init_eth:.2f}"
    startup_msg = f"🟢 监控系统 v5 已启动\n⏰ {start_time}{price_line}\n{'─'*24}\n📊 监控配置\n• BTC变动阈值: 0.3%\n• ETH变动阈值: 0.2%\n• BTC关键位: {btc_levels_str}\n• ETH关键位: {eth_levels_str}\n• 定时推送: 无（仅价格变动+关键位警报）\n⚠️ 有变动立刻通知"
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
