#!/usr/bin/env python3
"""
BTC + ETH 实时监控脚本 v3
- Gate.io API 无缓存实时数据
- 30秒检查一次（及时）
- 价格变动≥0.2%立刻推企微
- 触及关键位（±0.5%）立刻推企微
- 防崩：连续失败5次自动重启
- 企微推送失败写入本地日志
"""

import requests
import time
import os
import sys
from datetime import datetime

# ============ 配置区 ============
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"

# BTC关键价位（±0.5%区间触发）
BTC_LEVELS = {
    61500: "🟡 BTC触及61,500！可能见底，准备抄底",
    62000: "🔵 BTC触及62,000强支撑！重点关注，可能反弹",
    62400: "🟢 BTC触及62,400支撑！短线可能反弹",
    63000: "🟠 BTC触及63,000压力！可能受阻",
    63500: "🔴 BTC触及63,500强压力！做空机会",
    64500: "🟣 BTC触及64,500！突破看65,000",
}

# ETH关键价位
ETH_LEVELS = {
    1600: "🟡 ETH触及1,600！可能见底，准备抄底",
    1644: "🔵 ETH触及1,644强支撑（S2枢轴）！",
    1650: "🟢 ETH触及1,650支撑！短线可能反弹",
    1680: "🟠 ETH触及1,680压力！",
    1710: "🔴 ETH触及1,710强压力！做空机会",
    1750: "🟣 ETH触及1,750！突破看1,800",
}

CHECK_INTERVAL = 30      # 30秒检查一次
PRICE_CHANGE_THRESHOLD = 0.002  # 价格变动≥0.2%推送
MAX_FAILS_BEFORE_RESTART = 5     # 连续失败5次重启脚本
LOG_FILE = "/workspace/monitor_v3_fail.log"
# ============ 配置区结束 ============


def send_wechat(msg):
    """发送企微消息，失败写本地日志"""
    try:
        payload = {"msgtype": "text", "text": {"content": msg}}
        resp = requests.post(WECHAT_WEBHOOK, json=payload, timeout=5)
        result = resp.json()
        if result.get("errcode") == 0:
            print(f"  ✅ 企微推送成功")
            return True
        else:
            print(f"  ❌ 企微推送失败: {result}")
    except Exception as e:
        print(f"  ❌ 企微推送异常: {e}")
    # 推送失败，写本地日志备用
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now()}] PUSH_FAIL: {msg}\n")
    except:
        pass
    return False


def get_price(contract, retry=3):
    """获取Gate.io期货实时价格，失败自动重试"""
    for i in range(retry):
        try:
            headers = {
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            resp = requests.get(
                f'https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={contract}',
                headers=headers, timeout=10)
            data = resp.json()
            if isinstance(data, list) and data:
                return float(data[0]['last'])
        except Exception as e:
            print(f"  ⚠️ Gate.io {contract} 第{i+1}次失败: {e}")
            if i < retry - 1:
                time.sleep(2)
    return None


def check_price_alert(price, levels, threshold_pct):
    """检查价格是否在关键位±threshold_pct范围内"""
    hits = []
    for target, msg in levels.items():
        if abs(price - target) / target <= threshold_pct:
            hits.append((target, msg))
    return hits


def restart_script():
    """重启自身"""
    print("\n🔄 连续失败过多，重启脚本...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def main():
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("=" * 60)
    print("BTC + ETH 实时监控 v3 启动（Gate.io 无缓存）")
    print(f"启动时间: {start_time}")
    print(f"检查间隔: {CHECK_INTERVAL}秒")
    print(f"推送阈值: 价格变动≥{PRICE_CHANGE_THRESHOLD*100:.1f}%")
    print("=" * 60)

    # 启动时推送企微通知
    send_wechat(f"🟢 监控系统 v3 已启动\n⏰ {start_time}\n✅ 开始实时监控 BTC+ETH")

    alerted_btc = set()   # 本次运行已警报的BTC价位
    alerted_eth = set()   # 本次运行已警报的ETH价位
    last_btc = None        # 上次BTC价格（用于计算涨跌幅）
    last_eth = None        # 上次ETH价格
    last_btc_push = None   # 上次推送时的BTC价格（用于0.2%变动判断）
    last_eth_push = None   # 上次推送时的ETH价格
    fail_count = 0         # 连续获取价格失败次数
    loop_count = 0

    while True:
        try:
            loop_count += 1
            now = datetime.now().strftime('%H:%M:%S')

            # 获取实时价格
            btc = get_price("BTC_USDT")
            eth = get_price("ETH_USDT")

            # 失败计数
            if btc is None or eth is None:
                fail_count += 1
                print(f"[{now}] ⚠️ 获取价格失败({fail_count}/{MAX_FAILS_BEFORE_RESTART})")
                if fail_count >= MAX_FAILS_BEFORE_RESTART:
                    restart_script()
                time.sleep(CHECK_INTERVAL)
                continue
            fail_count = 0  # 成功，重置计数

            # 启动时初始化
            if last_btc_push is None:
                last_btc_push = btc
            if last_eth_push is None:
                last_eth_push = eth

            # 计算涨跌幅
            btc_change_str = ""
            eth_change_str = ""
            if last_btc:
                pct = (btc - last_btc) / last_btc * 100
                btc_change_str = f" ({pct:+.2f}%)"
            if last_eth:
                pct = (eth - last_eth) / last_eth * 100
                eth_change_str = f" ({pct:+.2f}%)"

            print(f"[{now}] BTC: ${btc:.1f}{btc_change_str} | ETH: ${eth:.2f}{eth_change_str}")

            # ===== 推送1：价格变动≥0.2% =====
            btc_push_pct = abs(btc - last_btc_push) / last_btc_push
            eth_push_pct = abs(eth - last_eth_push) / last_eth_push

            if btc_push_pct >= PRICE_CHANGE_THRESHOLD:
                direction = "📈" if btc > last_btc_push else "📉"
                msg = (f"{direction} BTC 价格变动提醒\n"
                       f"当前价：${btc:.1f}\n"
                       f"变动：{(btc - last_btc_push)/last_btc_push*100:+.2f}%\n"
                       f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  📤 BTC变动{btc_push_pct*100:.2f}%，推送企微...")
                send_wechat(msg)
                last_btc_push = btc
                # 价格已变动，重置关键位警报（可以再次推送）
                alerted_btc.clear()

            if eth_push_pct >= PRICE_CHANGE_THRESHOLD:
                direction = "📈" if eth > last_eth_push else "📉"
                msg = (f"{direction} ETH 价格变动提醒\n"
                       f"当前价：${eth:.2f}\n"
                       f"变动：{(eth - last_eth_push)/last_eth_push*100:+.2f}%\n"
                       f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  📤 ETH变动{eth_push_pct*100:.2f}%，推送企微...")
                send_wechat(msg)
                last_eth_push = eth
                alerted_eth.clear()

            # ===== 推送2：触及关键位 =====
            btc_hits = check_price_alert(btc, BTC_LEVELS, 0.005)
            for target, msg in btc_hits:
                key = f"btc_{target}"
                if key not in alerted_btc:
                    full_msg = (f"【BTC关键位警报】\n"
                                f"{msg}\n\n"
                                f"当前价: ${btc:.1f}\n"
                                f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"  🚨 BTC触及关键位${target}，推送企微...")
                    send_wechat(full_msg)
                    alerted_btc.add(key)

            eth_hits = check_price_alert(eth, ETH_LEVELS, 0.005)
            for target, msg in eth_hits:
                key = f"eth_{target}"
                if key not in alerted_eth:
                    full_msg = (f"【ETH关键位警报】\n"
                                f"{msg}\n\n"
                                f"当前价: ${eth:.2f}\n"
                                f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"  🚨 ETH触及关键位${target}，推送企微...")
                    send_wechat(full_msg)
                    alerted_eth.add(key)

            # 每10分钟打印一次安静状态（证明脚本还活着，但不推企微）
            if loop_count % 20 == 0:  # 20*30s = 10分钟
                print(f"  💤 监控正常，无警报（每10分钟状态确认）")

            last_btc = btc
            last_eth = eth
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n⏹️ 监控已停止")
            break
        except Exception as e:
            print(f"❌ 未捕获错误: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
