#!/usr/bin/env python3
"""
BTC + ETH 多时间框架监控脚本
- 3/5/15分钟 + 1小时关键位监控
- 到达后推送企微警报
- 每5分钟检查一次价格
"""

import requests
import time
from datetime import datetime
import json

# ============ 配置区 ============
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"  # ← 填你的企微webhook地址

# BTC关键价位（±0.5%区间触发）
BTC_LEVELS = {
    61500: {"type": "extreme_support", "message": "🟡 BTC触及61,500！可能见底，准备抄底"},
    62000: {"type": "strong_support", "message": "🔵 BTC触及62,000强支撑！重点关注，可能反弹"},
    62400: {"type": "support", "message": "🟢 BTC触及62,400支撑！短线可能反弹"},
    63000: {"type": "resistance", "message": "🟠 BTC触及63,000压力！可能受阻"},
    63500: {"type": "strong_resistance", "message": "🔴 BTC触及63,500强压力（EMA10）！做空机会"},
    64500: {"type": "extreme_resistance", "message": "🟣 BTC触及64,500！突破看65,000"},
}

# ETH关键价位
ETH_LEVELS = {
    1600: {"type": "extreme_support", "message": "🟡 ETH触及1,600！可能见底，准备抄底"},
    1644: {"type": "strong_support", "message": "🔵 ETH触及1,644强支撑（S2枢轴）！"},
    1650: {"type": "support", "message": "🟢 ETH触及1,650支撑！短线可能反弹"},
    1680: {"type": "resistance", "message": "🟠 ETH触及1,680压力！"},
    1710: {"type": "strong_resistance", "message": "🔴 ETH触及1,710强压力（EMA10）！做空机会"},
    1750: {"type": "extreme_resistance", "message": "🟣 ETH触及1,750！突破看1,800"},
}

CHECK_INTERVAL = 300  # 5分钟检查一次
# ============ 配置区结束 ============


def send_wechat_alert(message):
    """发送企微警报"""
    if not WECHAT_WEBHOOK:
        print(f"[企微未配置] {message}")
        return

    try:
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        resp = requests.post(WECHAT_WEBHOOK, json=payload, timeout=5)
        result = resp.json()
        if result.get("errcode") == 0:
            print(f"✅ 企微推送成功")
        else:
            print(f"❌ 企微推送失败: {result}")
    except Exception as e:
        print(f"❌ 企微推送失败: {e}")


def get_btc_price():
    """获取BTCUSDT价格（多数据源）"""
    sources = [
        {
            "name": "MEXC",
            "url": "https://api.mexc.com/api/v3/ticker/price?symbol=BTCUSDT",
            "parser": lambda d: float(d['price'])
        },
        {
            "name": "CoinGecko",
            "url": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            "parser": lambda d: float(d['bitcoin']['usd'])
        },
    ]

    for source in sources:
        try:
            resp = requests.get(source['url'], timeout=10)
            data = resp.json()
            price = source['parser'](data)
            return price
        except Exception as e:
            print(f"❌ {source['name']} 失败: {e}")
            continue

    return None


def get_eth_price():
    """获取ETHUSDT价格（多数据源）"""
    sources = [
        {
            "name": "MEXC",
            "url": "https://api.mexc.com/api/v3/ticker/price?symbol=ETHUSDT",
            "parser": lambda d: float(d['price'])
        },
        {
            "name": "CoinGecko",
            "url": "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd",
            "parser": lambda d: float(d['ethereum']['usd'])
        },
    ]

    for source in sources:
        try:
            resp = requests.get(source['url'], timeout=10)
            data = resp.json()
            price = source['parser'](data)
            return price
        except Exception as e:
            print(f"❌ {source['name']} 失败: {e}")
            continue

    return None


def check_levels(price, levels):
    """检查是否触及关键价位（±0.5%区间）"""
    alerts = []

    for target, config in levels.items():
        tolerance = target * 0.005  # 0.5%
        if abs(price - target) <= tolerance:
            alerts.append({
                "price": target,
                "config": config
            })

    return alerts


def main():
    """主监控循环"""
    print("=" * 60)
    print("BTC + ETH 多时间框架监控系统启动")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"检查间隔: {CHECK_INTERVAL}秒")
    print("=" * 60)

    alerted_btc = set()   # 已警报的BTC价位
    alerted_eth = set()   # 已警报的ETH价位
    last_btc = None
    last_eth = None

    while True:
        try:
            # 获取当前价格
            btc_price = get_btc_price()
            eth_price = get_eth_price()

            if btc_price is None or eth_price is None:
                print("⚠️ 无法获取价格，5分钟后重试...")
                time.sleep(CHECK_INTERVAL)
                continue

            # 计算涨跌幅
            btc_change = ""
            eth_change = ""
            if last_btc:
                btc_change = (btc_price - last_btc) / last_btc * 100
                btc_change_str = f"（{btc_change:+.2f}%）"
            else:
                btc_change_str = ""

            if last_eth:
                eth_change = (eth_price - last_eth) / last_eth * 100
                eth_change_str = f"（{eth_change:+.2f}%）"
            else:
                eth_change_str = ""

            now = datetime.now().strftime('%H:%M:%S')
            print(f"\n[{now}] BTC: {btc_price:.1f} {btc_change_str} | ETH: {eth_price:.2f} {eth_change_str}")

            # 检查BTC关键位
            btc_alerts = check_levels(btc_price, BTC_LEVELS)
            for alert in btc_alerts:
                key = f"btc_{alert['price']}"
                if key not in alerted_btc:
                    msg = f"""【BTC警报】
{alert['config']['message']}

当前价: {btc_price:.1f}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                    send_wechat_alert(msg)
                    alerted_btc.add(key)

            # 检查ETH关键位
            eth_alerts = check_levels(eth_price, ETH_LEVELS)
            for alert in eth_alerts:
                key = f"eth_{alert['price']}"
                if key not in alerted_eth:
                    msg = f"""【ETH警报】
{alert['config']['message']}

当前价: {eth_price:.2f}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                    send_wechat_alert(msg)
                    alerted_eth.add(key)

            # 每分钟输出一次状态（无警报时也输出）
            if int(time.time()) % 60 == 0:
                status_msg = f"📊 BTC+ETH监控中...\nBTC: {btc_price:.1f} | ETH: {eth_price:.2f}\n监控价位: BTC {list(BTC_LEVELS.keys())}\n          ETH {list(ETH_LEVELS.keys())}"
                print(status_msg)

            last_btc = btc_price
            last_eth = eth_price

            # 等待下次检查
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n⏹️ 监控已停止")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
