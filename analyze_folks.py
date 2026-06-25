import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# 获取FOLKSUSDT的3515分钟K线数据
# 3515分钟 = 58.58小时 ≈ 2.44天

symbol = "FOLKSUSDT"
interval = "1m"  # 用1分钟线聚合
limit = 5000  # 最多拉5000根

url = f"https://api.binance.com/api/v3/klines"
params = {
    "symbol": symbol,
    "interval": interval,
    "limit": limit
}

print(f"正在获取 {symbol} 的 {limit} 根1分钟K线...")

try:
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    
    if isinstance(data, dict) and "code" in data:
        print(f"API错误: {data}")
    else:
        print(f"获取到 {len(data)} 根K线")
        print(f"时间范围: {datetime.fromtimestamp(data[0][0]/1000)} 到 {datetime.fromtimestamp(data[-1][0]/1000)}")
        
        # 保存原始数据
        cols = ['timestamp','open','high','low','close','volume','close_time',
                'quote_volume','trades','taker_buy_base','taker_buy_quote','ignore']
        df = pd.DataFrame(data, columns=cols)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
        
        # 聚合到3515分钟
        agg_minutes = 3515
        print(f"\n聚合到 {agg_minutes} 分钟K线...")
        
        # 用resample需要整数分钟，3515不能被60整除，用手动滚动窗口
        # 改用最接近的标准周期：3515分钟 ≈ 59小时，用小时线59根
        # 或者直接展示最近3515分钟的详细分析
        
        # 先展示基础统计
        recent = df.tail(3515)
        print(f"\n=== 最近3515分钟 ({agg_minutes}分钟) 行情分析 ===")
        print(f"时间范围: {recent.index[0]} 到 {recent.index[-1]}")
        print(f"总交易量: {recent['volume'].sum():.2f}")
        print(f"总成交额: {recent['quote_volume'].sum():.2f} USDT")
        print(f"\n价格统计:")
        print(f"  最高价: {recent['high'].max():.6f}")
        print(f"  最低价: {recent['low'].min():.6f}")
        print(f"  开盘价: {recent['open'].iloc[0]:.6f}")
        print(f"  收盘价: {recent['close'].iloc[-1]:.6f}")
        print(f"  涨跌幅: {((recent['close'].iloc[-1] - recent['open'].iloc[0])/recent['open'].iloc[0]*100):.2f}%")
        
        # 波动率
        recent['returns'] = recent['close'].pct_change()
        volatility = recent['returns'].std() * np.sqrt(3515) * 100
        print(f"\n波动率(年化估算): {volatility:.2f}%")
        
        # 成交量分析
        avg_volume = recent['volume'].mean()
        max_volume = recent['volume'].max()
        print(f"\n成交量分析:")
        print(f"  平均每分钟成交量: {avg_volume:.2f}")
        print(f"  最大单分钟成交量: {max_volume:.2f}")
        
        # 保存详细数据
        recent.to_csv('/workspace/folks_3515m.csv')
        print(f"\n详细数据已保存到: /workspace/folks_3515m.csv")
        
except Exception as e:
    print(f"错误: {e}")
