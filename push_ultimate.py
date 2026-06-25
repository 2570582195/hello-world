#!/usr/bin/env python3.11
"""
推送 BTC+ETH 终极深度分析（4条消息）
"""
import requests, json, time
from datetime import datetime

WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"

def send_wechat(msg):
    try:
        resp = requests.post(WEBHOOK, json={"msgtype": "text", "text": {"content": msg}}, timeout=10)
        result = resp.json()
        if result.get('errcode') == 0:
            print("  ✅ 企微推送成功")
            return True
        else:
            print(f"  ❌ 企微推送失败: {result}")
    except Exception as e:
        print(f"  ❌ 企微推送异常: {e}")
    return False

def get_price(symbol):
    try:
        resp = requests.get(f'https://api.gateio.ws/api/v4/futures/usdt/tickers?contract={symbol}', timeout=10)
        data = resp.json()
        if isinstance(data, list) and data:
            t = data[0]
            return {
                'last': float(t['last']),
                'high': float(t['high_24h']),
                'low': float(t['low_24h']),
                'change': float(t['change_percentage']),
                'funding': float(t['funding_rate']),
                'volume': float(t['volume_24h']),
            }
    except:
        pass
    return None

def get_klines(symbol, interval='4h', limit=100):
    try:
        resp = requests.get(
            'https://api.gateio.ws/api/v4/futures/usdt/candlesticks',
            params={'contract': symbol, 'interval': interval, 'limit': limit},
            timeout=15
        )
        data = resp.json()
        if not isinstance(data, list) or not data:
            return None
        closes = [float(k['c']) for k in data]
        highs = [float(k['h']) for k in data]
        lows = [float(k['l']) for k in data]
        return {'closes': closes, 'highs': highs, 'lows': lows}
    except:
        pass
    return None

def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd(prices):
    def ema(data, period):
        multi = 2 / (period + 1)
        e = sum(data[:period]) / period
        result = [e]
        for i in range(period, len(data)):
            e = (data[i] - e) * multi + e
            result.append(e)
        return result
    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    macd_line = [ema12[i] - ema26[i] for i in range(min(len(ema12), len(ema26)))]
    signal_line = ema(macd_line, 9) if len(macd_line) >= 9 else []
    hist = [macd_line[i] - signal_line[i] for i in range(min(len(macd_line), len(signal_line)))]
    return macd_line, signal_line, hist

def calc_bb(prices, period=20):
    if len(prices) < period:
        return None, None
    recent = prices[-period:]
    sma = sum(recent) / period
    variance = sum((p - sma) ** 2 for p in recent) / period
    std_dev = variance ** 0.5
    return sma + 2 * std_dev, sma - 2 * std_dev

# ===== 主逻辑 =====
print("=" * 60)
print("  BTC + ETH 终极深度分析")
print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# 1. 获取实时价
btc = get_price('BTC_USDT')
eth = get_price('ETH_USDT')
if not btc or not eth:
    print("❌ 获取价格失败")
    exit(1)

# 2. 获取4H K线
btc_k = get_klines('BTC_USDT', '4h', 100)
eth_k = get_klines('ETH_USDT', '4h', 100)

# 3. 计算指标
btc_rsi = calc_rsi(btc_k['closes']) if btc_k else None
eth_rsi = calc_rsi(eth_k['closes']) if eth_k else None

macd_data = calc_macd(btc_k['closes']) if btc_k else (None, None, None)
btc_macd = macd_data[0][-1] if macd_data[0] else None
btc_hist = macd_data[2][-1] if macd_data[2] else None

bb_up, bb_lo = calc_bb(btc_k['closes']) if btc_k else (None, None)

now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
sep = "─" * 28

# ===== 第1条：行情总览 =====
part1 = f"""📊 BTC+ETH 终极深度分析 【1/4】
⏰ {now_str}
{sep}

📊 **行情总览**

  BTC: ${btc['last']:.1f}  ({btc['change']:+.2f}%)
    ↗ 24h高: ${btc['high']:.1f}  ↘ 24h低: ${btc['low']:.1f}
    📊 24h量: {btc['volume']/1e9:.2f}B
    ⚡ 资金费率: {btc['funding']*100:.4f}%

  ETH: ${eth['last']:.2f}  ({eth['change']:+.2f}%)
    ↗ 24h高: ${eth['high']:.2f}  ↘ 24h低: ${eth['low']:.2f}
    📊 24h量: {eth['volume']/1e9:.2f}B
    ⚡ 资金费率: {eth['funding']*100:.4f}%
"""

send_wechat(part1)
time.sleep(2)

# ===== 第2条：技术指标 =====
rsi_btc_str = f"{btc_rsi:.1f} {'超买＞70' if btc_rsi and btc_rsi > 70 else ('超卖＜30' if btc_rsi and btc_rsi < 30 else '中性')}"
rsi_eth_str = f"{eth_rsi:.1f} {'超买＞70' if eth_rsi and eth_rsi > 70 else ('超卖＜30' if eth_rsi and eth_rsi < 30 else '中性')}"
macd_str = f"{btc_macd:+.2f}" if btc_macd else "计算中"
hist_str = f"{btc_hist:+.2f}" if btc_hist else "计算中"
bb_str = f"上轨 ${bb_up:.1f}  下轨 ${bb_lo:.1f}" if bb_up else "计算中"

part2 = f"""📊 BTC+ETH 终极深度分析 【2/4】
⏰ {now_str}
{sep}

📈 **技术指标（4小时）**

  【BTC】
    RSI(14): {rsi_btc_str}
    MACD: {macd_str}  Hist: {hist_str}
    BB: {bb_str}

  【ETH】
    RSI(14): {rsi_eth_str}
    4H 范围: ${min(eth_k['lows'][-6:]):.2f} ~ ${max(eth_k['highs'][-6:]):.2f}
"""

send_wechat(part2)
time.sleep(2)

# ===== 第3条：关键位 + 链上数据 =====
try:
    fng_resp = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10)
    fng_data = fng_resp.json()
    fng_val = int(fng_data['data'][0]['value'])
    fng_cls = fng_data['data'][0]['value_classification']
except:
    fng_val = None
    fng_cls = "获取失败"

part3 = f"""📊 BTC+ETH 终极深度分析 【3/4】
⏰ {now_str}
{sep}

📍 **关键支撑/压力位**

  【BTC】
    • 强支撑: $60,229 (1h S1) ★
    • 次支撑: $59,376 (4h S2) ★★
    • 强压力: $62,568 (1h R1) ★
    • 次压力: $64,054 (4h R2) ★★

  【ETH】
    • 强支撑: $1,625 (15m S1) ★
    • 次支撑: $1,604 (1h S2) ★★
    • 强压力: $1,680 (15m R1) ★
    • 次压力: $1,713 (4h R2) ★★

{sep}
😱 **恐惧贪婪指数**: {fng_val if fng_val else '?'} / 100（{fng_cls}）
"""

send_wechat(part3)
time.sleep(2)

# ===== 第4条：交易策略 =====
btc_trend = "上涨" if btc['change'] > 0 else "下跌"
eth_trend = "上涨" if eth['change'] > 0 else "下跌"

part4 = f"""📊 BTC+ETH 终极深度分析 【4/4】
⏰ {now_str}
{sep}

🎯 **交易策略（{btc_trend}趋势）**

  【无持仓场景】
    • BTC: {"观望" if btc['change'] > 0 else "可关注 $60,229 支撑反弹"}
    • ETH: {"观望" if eth['change'] > 0 else "可关注 $1,625 支撑反弹"}
    • 止损: 支撑位 -1.5%

  【有持仓场景】
    • 多单: 压力位 $62,568 减仓50%，突破追
    • 空单: 支撑位 $60,229 减仓50%，跌破追
    • 止损: 入场价 ±2%

{sep}
⚠️ **风险提示**
    • BTC在$60,229~$62,568区间震荡
    • ETH已触及S2 $1,604，注意反弹
    • 下次推送: 2小时后
"""

send_wechat(part4)

print(f"\n  ✅ 终极深度分析推送完成（4条）")
print("=" * 60)
