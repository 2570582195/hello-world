#!/usr/bin/env python3.11
"""
FOLKSUSDT 价格监控系统
监控关键价位：2.74 / 2.82 / 2.85 / 2.90
到达后通过企微推送警报
"""

import requests
import time
import json
from datetime import datetime

# ============ 配置区 ============
WEBHOOK_URL = ""  # 企微机器人webhook地址，需要你填

ALERT_PRICES = {
    "2.74": {"type": "support", "message": "🔵 FOLKS触及支撑位2.74！可能反弹，检查空单！"},
    "2.78": {"type": "cost_avg", "message": "⚠️ FOLKS到达你的平均成本2.78！准备移动止损！"},
    "2.82": {"type": "breakeven", "message": "🚨 FOLKS突破2.82！空单开始浮亏，考虑平仓或设止损！"},
    "2.85": {"type": "resistance", "message": "🔴 FOLKS触及压力位2.85！如果突破，可能冲击2.90！"},
    "2.90": {"type": "stop_loss", "message": "💀 FOLKS突破2.90！立刻止损！别犹豫！"},
}

CHECK_INTERVAL = 300  # 5分钟检查一次
# ============ 配置区结束 ============

def send_wecom_alert(message):
    """发送企微警报"""
    if not WEBHOOK_URL:
        print(f"[企微未配置] {message}")
        return
    
    try:
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        resp = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        print(f"✅ 企微推送成功: {message[:50]}...")
    except Exception as e:
        print(f"❌ 企微推送失败: {e}")

def get_folks_price():
    """获取FOLKSUSDT当前价格（多数据源）"""
    sources = [
        {
            "name": "MEXC",
            "url": "https://api.mexc.com/api/v3/ticker/price?symbol=FOLKSUSDT",
            "parser": lambda d: float(d['price'])
        },
        {
            "name": "Gate.io",
            "url": "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=FOLKS_USDT",
            "parser": lambda d: float(d[0]['last'])
        },
        {
            "name": "CoinGecko",
            "url": "https://api.coingecko.com/api/v3/simple/price?ids=folks-finance&vs_currencies=usd",
            "parser": lambda d: float(d['folks-finance']['usd'])
        },
    ]
    
    for source in sources:
        try:
            resp = requests.get(source['url'], timeout=10)
            data = resp.json()
            price = source['parser'](data)
            print(f"✅ {source['name']} 价格: {price}")
            return price
        except Exception as e:
            print(f"❌ {source['name']} 失败: {e}")
            continue
    
    return None

def check_alerts(current_price, alerted_prices):
    """检查是否触及警报价位"""
    alerts = []
    
    for target_str, config in ALERT_PRICES.items():
        target = float(target_str)
        
        # 如果已经警报过，跳过
        if target_str in alerted_prices:
            continue
        
        # 检查是否触及（±0.5%区间）
        tolerance = target * 0.005  # 0.5%
        
        if abs(current_price - target) <= tolerance:
            alerts.append({
                "price": target_str,
                "config": config
            })
            alerted_prices.add(target_str)
    
    return alerts

def main():
    """主监控循环"""
    print("=" * 60)
    print("FOLKSUSDT 价格监控系统启动")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    alerted_prices = set()  # 已警报的价格（避免重复）
    last_price = None
    
    while True:
        try:
            # 获取当前价格
            current_price = get_folks_price()
            
            if current_price is None:
                print("⚠️ 无法获取价格，5分钟后重试...")
                time.sleep(CHECK_INTERVAL)
                continue
            
            # 计算涨跌幅
            change_str = ""
            if last_price:
                change = (current_price - last_price) / last_price * 100
                change_str = f"（{change:+.2f}%）"
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 当前价格: {current_price:.4f} {change_str}")
            
            # 检查警报
            alerts = check_alerts(current_price, alerted_prices)
            
            for alert in alerts:
                message = f"{alert['config']['message']}\n\n当前价: {current_price:.4f}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                send_wecom_alert(message)
            
            # 每分钟输出一次状态（无警报时也输出）
            if int(time.time()) % 60 == 0:
                status_msg = f"📊 FOLKS监控中...\n当前价: {current_price:.4f}\n监控价位: {', '.join(ALERT_PRICES.keys())}"
                print(status_msg)
            
            last_price = current_price
            
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
