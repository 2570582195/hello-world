#!/usr/bin/env python3
"""
BTC + ETH 实时监控脚本 v4
- Gate.io API 无缓存实时数据（30秒检查）
- 价格变动≥0.2%立刻推企微
- 触及关键位（±0.5%）立刻推企微
- 每2小时自动推送链上深度数据（恐惧指数/爆仓/OI/算力等）
- 防崩：SSL失败重试3次，连续5次失败自动重启
- 启动时推送通知
"""

import requests
import time
import os
import sys
import json
from datetime import datetime

# ============ 配置区 ============
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"

BTC_LEVELS = {
    61500: "🟡 BTC触及61,500！可能见底，准备抄底",
    62000: "🔵 BTC触及62,000强支撑！重点关注，可能反弹",
    62400: "🟢 BTC触及62,400支撑！短线可能反弹",
    63000: "🟠 BTC触及63,000压力！可能受阻",
    63500: "🔴 BTC触及63,500强压力！做空机会",
    64500: "🟣 BTC触及64,500！突破看65,000",
}

ETH_LEVELS = {
    1600: "🟡 ETH触及1,600！可能见底，准备抄底",
    1644: "🔵 ETH触及1,644强支撑（S2枢轴）！",
    1650: "🟢 ETH触及1,650支撑！短线可能反弹",
    1680: "🟠 ETH触及1,680压力！",
    1710: "🔴 ETH触及1,710强压力！做空机会",
    1750: "🟣 ETH触及1,750！突破看1,800",
}

CHECK_INTERVAL = 30
PRICE_CHANGE_THRESHOLD = 0.002
MAX_FAILS_BEFORE_RESTART = 5
ONCHAIN_INTERVAL = 7200  # 2小时推送一次链上数据
LOG_FILE = "/workspace/monitor_v4.log"
FAIL_LOG = "/workspace/monitor_v4_fail.log"

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
    # 推送失败写日志
    try:
        with open(FAIL_LOG, "a") as f:
            f.write(f"[{datetime.now()}] PUSH_FAIL: {msg}\n")
    except:
        pass
    return False


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


def get_fear_greed():
    """获取恐惧贪婪指数"""
    try:
        resp = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10)
        data = resp.json()
        fng = data['data'][0]
        return int(fng['value']), fng['value_classification']
    except:
        return None, None


def get_btc_onchain():
    """获取BTC链上数据（blockchain.com）"""
    result = {}
    urls = {
        'tx_count': 'https://blockchain.info/q/24hrtransactioncount',
        'difficulty': 'https://blockchain.info/q/getdifficulty',
        'hashrate': 'https://blockchain.info/q/hashrate',
        'total_btc': 'https://blockchain.info/q/totalbc',
        'avg_price': 'https://blockchain.info/q/24hrprice',
    }
    for key, url in urls.items():
        try:
            resp = requests.get(url, timeout=10)
            result[key] = resp.text.strip()
        except:
            result[key] = None
    return result


def get_market_caps():
    """获取市值数据（Coinlore）"""
    try:
        resp = requests.get('https://api.coinlore.net/api/ticker/?id=90,80', timeout=10)
        data = resp.json()
        caps = {}
        for coin in data:
            caps[coin['symbol']] = {
                'price': float(coin['price_usd']),
                'change': float(coin['percent_change_24h']),
                'mcap': float(coin['market_cap_usd']),
                'vol24': float(coin['volume24']),
            }
        return caps
    except:
        return {}


def get_market_crash_top():
    """获取全市场暴跌TOP10（Gate.io全合约）"""
    try:
        resp = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers',
                           headers=HEADERS, timeout=10)
        data = resp.json()
        sorted_drop = sorted(data, key=lambda x: float(x.get('change_percentage', 0)))[:10]
        return [(t['contract'], t['last'], t['change_percentage']) for t in sorted_drop]
    except:
        return []


def push_onchain_data():
    """推送链上深度数据（每2小时一次）"""
    print(f"\n📡 开始抓取链上深度数据...")
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 恐惧指数
    fng_val, fng_class = get_fear_greed()

    # Gate.io实时ticker
    btc_t = get_gate_ticker("BTC_USDT")
    eth_t = get_gate_ticker("ETH_USDT")

    # BTC链上
    onchain = get_btc_onchain()

    # 市值
    caps = get_market_caps()

    # 暴跌排行
    crash_top = get_market_crash_top()

    # 组装消息第1条
    part1 = f"📡 链上深度数据定时推送 【1/2】\n⏰ {now_str}\n━━━━━━━━━━━━━━━━━━\n"

    if fng_val is not None:
        part1 += f"😱 恐惧贪婪指数：{fng_val}/100（{fng_class}）\n"
        if fng_val < 25:
            part1 += "→ 极度恐惧，中期反向偏多信号\n"
        elif fng_val < 45:
            part1 += "→ 恐惧，观望为主\n"
        elif fng_val > 75:
            part1 += "→ 极度贪婪，注意回调风险\n"
        part1 += "\n"

    if btc_t:
        part1 += f"🔵 BTC ${btc_t['last']}\n"
        part1 += f"  24h: {btc_t['change_percentage']}% | 高${btc_t['high_24h']} 低${btc_t['low_24h']}\n"
        part1 += f"  OI: {float(btc_t['total_size'])/1e6:.1f}M USDT | 费率: {btc_t['funding_rate']}\n\n"
    if eth_t:
        part1 += f"🔵 ETH ${eth_t['last']}\n"
        part1 += f"  24h: {eth_t['change_percentage']}% | 高${eth_t['high_24h']} 低${eth_t['low_24h']}\n"
        part1 += f"  OI: {float(eth_t['total_size'])/1e6:.1f}M USDT | 费率: {eth_t['funding_rate']}\n"

    part1 += "\n━━━━━━━━━━━━━━━━━━\n"
    part1 += "⛏️ BTC链上数据（Blockchain.com）\n"
    if onchain.get('tx_count'):
        part1 += f"  24h交易数: {int(onchain['tx_count']):,}笔\n"
    if onchain.get('hashrate'):
        hs = float(onchain['hashrate']) / 1e12
        part1 += f"  算力: {hs:.0f} TH/s ({hs/1e6:.2f} EH/s)\n"
    if onchain.get('total_btc'):
        part1 += f"  已挖出: {int(onchain['total_btc'])/1e8:,.0f} BTC\n"
    if onchain.get('difficulty'):
        part1 += f"  难度: {float(onchain['difficulty']):.2e}\n"

    send_wechat(part1)

    # 组装消息第2条
    time.sleep(2)
    part2 = f"📡 链上深度数据定时推送 【2/2】\n⏰ {now_str}\n━━━━━━━━━━━━━━━━━━\n"

    if caps:
        if 'BTC' in caps:
            b = caps['BTC']
            part2 += f"💰 BTC市值: ${b['mcap']/1e9:.1f}B | 24h量: ${b['vol24']/1e9:.1f}B\n"
        if 'ETH' in caps:
            e = caps['ETH']
            part2 += f"💰 ETH市值: ${e['mcap']/1e9:.1f}B | 24h量: ${e['vol24']/1e9:.1f}B\n"

    part2 += "\n━━━━━━━━━━━━━━━━━━\n"
    part2 += "📉 全市场暴跌TOP10（Gate.io期货）\n"
    if crash_top:
        for i, (contract, price, change) in enumerate(crash_top, 1):
            part2 += f"  {i}. {contract}: {price} ({change}%)\n"

    part2 += "\n━━━━━━━━━━━━━━━━━━\n"
    part2 += "🎯 链上信号总结\n"
    if fng_val is not None and fng_val < 25:
        part2 += "• 恐惧指数极低 → 中期底部信号\n"
    if btc_t and float(btc_t.get('funding_rate', 0)) < 0:
        part2 += "• BTC费率为负 → 空头付费，可能反转\n"
    if eth_t and float(eth_t.get('funding_rate', 0)) < 0:
        part2 += "• ETH费率为负 → 空头过度，注意挤压\n"
    part2 += "• 下次推送: 2小时后"

    send_wechat(part2)
    print(f"  ✅ 链上数据推送完成\n")


def restart_script():
    """重启自身"""
    print("\n🔄 连续失败过多，重启脚本...")
    send_wechat(f"🔄 监控脚本自动重启\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n原因: API连续失败")
    time.sleep(3)
    os.execv(sys.executable, [sys.executable] + sys.argv)


def main():
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print("=" * 60)
    print("BTC + ETH 实时监控 v4 启动")
    print(f"启动时间: {start_time}")
    print(f"检查间隔: {CHECK_INTERVAL}秒 | 链上数据: 每{ONCHAIN_INTERVAL//3600}小时")
    print("=" * 60, flush=True)

    # 启动通知
    send_wechat(f"🟢 监控系统 v4 已启动\n⏰ {start_time}\n✅ 实时监控 BTC+ETH\n📡 链上数据每2小时推送\n⚠️ 有变动立刻通知你")

    alerted_btc = set()
    alerted_eth = set()
    last_btc = None
    last_eth = None
    last_btc_push = None
    last_eth_push = None
    fail_count = 0
    loop_count = 0
    last_onchain_push = 0  # 上次链上数据推送时间

    while True:
        try:
            loop_count += 1
            now_ts = time.time()
            now = datetime.now().strftime('%H:%M:%S')

            # 检查是否需要推送链上数据
            if now_ts - last_onchain_push >= ONCHAIN_INTERVAL:
                try:
                    push_onchain_data()
                    last_onchain_push = now_ts
                except Exception as e:
                    print(f"  ❌ 链上数据推送失败: {e}")

            # 获取实时价格
            btc = get_price("BTC_USDT")
            eth = get_price("ETH_USDT")

            if btc is None or eth is None:
                fail_count += 1
                print(f"[{now}] ⚠️ 获取价格失败({fail_count}/{MAX_FAILS_BEFORE_RESTART})")
                if fail_count >= MAX_FAILS_BEFORE_RESTART:
                    restart_script()
                time.sleep(CHECK_INTERVAL)
                continue
            fail_count = 0

            # 初始化
            if last_btc_push is None:
                last_btc_push = btc
            if last_eth_push is None:
                last_eth_push = eth

            # 涨跌幅
            btc_chg = ""
            eth_chg = ""
            if last_btc:
                btc_chg = f" ({(btc-last_btc)/last_btc*100:+.2f}%)"
            if last_eth:
                eth_chg = f" ({(eth-last_eth)/last_eth*100:+.2f}%)"

            print(f"[{now}] BTC: ${btc:.1f}{btc_chg} | ETH: ${eth:.2f}{eth_chg}", flush=True)

            # 价格变动≥0.2%推送
            btc_pct = abs(btc - last_btc_push) / last_btc_push
            eth_pct = abs(eth - last_eth_push) / last_eth_push

            if btc_pct >= PRICE_CHANGE_THRESHOLD:
                direction = "📈" if btc > last_btc_push else "📉"
                send_wechat(f"{direction} BTC 价格变动\n当前价：${btc:.1f}\n变动：{(btc-last_btc_push)/last_btc_push*100:+.2f}%\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                last_btc_push = btc
                alerted_btc.clear()

            if eth_pct >= PRICE_CHANGE_THRESHOLD:
                direction = "📈" if eth > last_eth_push else "📉"
                send_wechat(f"{direction} ETH 价格变动\n当前价：${eth:.2f}\n变动：{(eth-last_eth_push)/last_eth_push*100:+.2f}%\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                last_eth_push = eth
                alerted_eth.clear()

            # 关键位检查
            for target, msg in BTC_LEVELS.items():
                if abs(btc - target) / target <= 0.005:
                    key = f"btc_{target}"
                    if key not in alerted_btc:
                        send_wechat(f"【BTC关键位警报】\n{msg}\n\n当前价: ${btc:.1f}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        alerted_btc.add(key)

            for target, msg in ETH_LEVELS.items():
                if abs(eth - target) / target <= 0.005:
                    key = f"eth_{target}"
                    if key not in alerted_eth:
                        send_wechat(f"【ETH关键位警报】\n{msg}\n\n当前价: ${eth:.2f}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        alerted_eth.add(key)

            # 10分钟状态确认
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
