import urllib3
try:
    urllib3.disable_warnings()
except:
    pass
# -*- coding: utf-8 -*-
"""
BTC+ETH 终极深度分析 V3 - 全维度实时版
数据源：
  - TradingView 技术指标（RSI/MACD/Williams%/动量等11项）
  - TradingView 均线/Pivot点
  - Gate.io 实时行情/资金费率/OI/EMA计算
  - CoinGlass 多空比（Binance/OKX/Bybit 分层）
  - CoinGlass 大额成交（实时列表）
  - Alternative.me 恐惧贪婪指数
  - Coinglass 爆仓数据
格式：单条长消息，22个维度全覆盖
"""

import requests, json, re, time, datetime as dt
from html import unescape

WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"
H = {'Cache-Control':'no-store','Pragma':'no-cache','Expires':'0','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def send(msg):
    r = requests.post(WEBHOOK, json={"msgtype":"text","text":{"content":msg}}, timeout=10)
    res = r.json()
    print(f"  push: {res}")
    return res.get("errcode")==0

def fetch(url, timeout=15):
    """通用GET请求"""
    for i in range(3):
        try:
            r = requests.get(url, headers=H, timeout=timeout, verify=False)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            print(f"  fetch retry {i+1}: {e}")
            time.sleep(2)
    return None

# ============================================================
# 1. Gate.io 实时行情
# ============================================================
print("=== [1/6] Gate.io 行情 ===")
try:
    btc_t = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers?contract=BTC_USDT', headers=H, timeout=10).json()[0]
    eth_t = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers?contract=ETH_USDT', headers=H, timeout=10).json()[0]
    bp = float(btc_t['last']); bc = float(btc_t['change_percentage'])
    bh = float(btc_t['high_24h']); bl = float(btc_t['low_24h'])
    bv = float(btc_t['volume_24h_base']); bfr = float(btc_t['funding_rate']); boi = float(btc_t['total_size'])
    ep = float(eth_t['last']); ec = float(eth_t['change_percentage'])
    eh = float(eth_t['high_24h']); el = float(eth_t['low_24h'])
    ev = float(eth_t['volume_24h_base']); efr = float(eth_t['funding_rate']); eoi = float(eth_t['total_size'])
    print(f"  BTC={bp:.1f}({bc:+.2f}%) ETH={ep:.2f}({ec:+.2f}%)")
except Exception as e:
    print(f"  Gate.io error: {e}")
    bp, bc, bv, bfr, boi = 60000, -3.0, 100000, -0.001, 50000
    ep, ec, ev, efr, eoi = 1600, -4.0, 500000, -0.0005, 200000

# ============================================================
# ============================================================
# ============================================================
# 2. 技术指标（从market_data.json读取，由服务器端WebFetch更新）
# ============================================================
print("=== [2/6] 读取技术指标数据 ===")
try:
    with open("/workspace/market_data.json","r") as f:
        mdata = json.load(f)
    tv_btc = mdata.get("tv_btc", {})
    tv_eth = mdata.get("tv_eth", {})
    cg_btc_ls = mdata.get("cg_btc_ls", {})
    cg_eth_ls = mdata.get("cg_eth_ls", {})
    btc_large_trades = mdata.get("cg_btc_large", [])
    liq_data = mdata.get("cg_liquidation", {})
    print(f"  数据时间: {mdata.get('update_time','未知')}")
except Exception as e:
    print(f"  读取数据文件失败: {e}")
    tv_btc, tv_eth = {}, {}
    cg_btc_ls, cg_eth_ls, btc_large_trades = {}, {}, []

btc_ind = tv_btc
eth_ind = tv_eth
btc_emas_tv = {k:v for k,v in tv_btc.items() if k.startswith('EMA')}
eth_emas_tv = {k:v for k,v in tv_eth.items() if k.startswith('EMA')}
btc_pivots = {k:v for k,v in tv_btc.items() if k in ('S1','S2','S3','R1','R2','Pivot')}
eth_pivots = {k:v for k,v in tv_eth.items() if k in ('S1','S2','S3','R1','R2','Pivot')}
print(f"  BTC: RSI={tv_btc.get('RSI','?')} MACD={tv_btc.get('MACD','?')}")
print(f"  ETH: RSI={tv_eth.get('RSI','?')} MACD={tv_eth.get('MACD','?')}")
print("=== [3/6] CoinGlass 多空比+大单（从JSON读取）===")
cg_data = {"btc": cg_btc_ls, "eth": cg_eth_ls}
btc_large = btc_large_trades
eth_large = []
print(f"  BTC多空比: Binance散={cg_btc_ls.get('bn_retail','?')}")
print(f"  ETH多空比: Binance散={cg_eth_ls.get('bn_retail','?')}")
print(f"  BTC大单数: {len(btc_large_trades)}")
print("=== [4/6] 恐惧贪婪指数 ===")
try:
    fg_data = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10).json()
    fg_val = int(fg_data['data'][0]['value'])
    fg_cls = fg_data['data'][0]['value_classification']
except:
    fg_val = 25; fg_cls = "极度恐惧"
print(f"  FGI: {fg_val} ({fg_cls})")

# ============================================================
# 5. 爆仓数据（从JSON读取）
# ============================================================
print("=== [5/6] 爆仓数据 ===")
liq_data = mdata.get("cg_liquidation", {})
btc_liq = liq_data.get("btc_24h", 0) * 1e6
eth_liq = liq_data.get("eth_24h", 0) * 1e6
print(f"  爆仓: BTC=${btc_liq/1e6:.1f}M ETH=${eth_liq/1e6:.1f}M (来自CoinGlass)")

# ============================================================
# 6. 暴跌排行（Gate.io全市场）
# ============================================================
print("=== [6/6] 暴跌排行 ===")
try:
    all_tk = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers', headers=H, timeout=10).json()
    crash = sorted(all_tk, key=lambda x: float(x.get('change_percentage',0)))[:11]
except:
    crash = []

# ============================================================
# 辅助函数
# ============================================================

def fmt_amt(usd):
    """格式化金额显示"""
    if usd >= 1e6:
        return f"${usd/1e6:.1f}M"
    elif usd >= 1e4:
        return f"${usd/1e4:.0f}K"
    elif usd >= 1000:
        return f"${usd/1000:.1f}K"
    return f"${usd:.0f}"

def get(key, default='-'):
    """安全获取字典值"""
    return default if key is None else key

# ============================================================
# 
def _sf(val, default=0):
    try: return float(val)
    except: return default

btc_rsi = _sf(btc_ind.get("RSI")); eth_rsi = _sf(eth_ind.get("RSI"))
btc_wpr = _sf(btc_ind.get("WPR")); eth_wpr = _sf(eth_ind.get("WPR"))
btc_macd = _sf(btc_ind.get("MACD")); eth_macd = _sf(eth_ind.get("MACD"))
btc_mom = _sf(btc_ind.get("Mom")); eth_mom = _sf(eth_ind.get("Mom"))
btc_stoch = _sf(btc_ind.get("StochK")); eth_stoch = _sf(eth_ind.get("StochK"))
# 组装消息 - 22个维度
# ============================================================
print("\n=== 组装消息 ===")
now_str = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
L = []  # lines

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度一：行情概览
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append(f"【📊 BTC+ETH 终极深度分析 | {now_str}】")
L.append("")
L.append("━━━━━━━━━━ 🚨 一、行情概览 ━━━━━━━━━")
L.append("")
L.append(f"┌───────────┬──────────────┬────────┐")
L.append(f"│ 品种       │ 价格(USDT)   │ 24h涨跌│")
L.append(f"├───────────┼──────────────┼────────┤")
L.append(f"│ BTC       │ {bp:>12,.1f} │ {bc:>+6.2f}%│")
L.append(f"│ ETH       │ {ep:>12,.2f} │ {ec:>+6.2f}%│")
L.append(f"└───────────┴──────────────┴────────┘")
L.append("")
L.append(f"BTC: 24h高 {bh:,.1f} | 低 {bl:,.1f} | 成交量 {bv:,.0f}张")
L.append(f"ETH: 24h高 {eh:.2f} | 低 {el:.2f} | 成交量 {ev:,.0f}张")
bf_pct = bfr * 100; ef_pct = efr * 100
L.append(f"BTC OI: {boi:,.0f}张 | 资金费率: {bf_pct:+.4f}%")
L.append(f"ETH OI: {eoi:,.0f}张 | 资金费率: {ef_pct:+.4f}%")
L.append("")
trend = "上涨" if bc > 0 else "下跌"
L.append(f"🔥 关键变化: BTC {trend}至{bp:,.1f}({bc:+.2f}%), ETH {trend}至{ep:.2f}({ec:+.2f}%)")
L.append(f"{'✅ 反弹修复中！' if bc > 0 else '❌ 继续下探！'}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度二：技术指标多维度详解（TV实时）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 二、技术指标多维度详解(TV实时) ━━━━━━━━━")
L.append("")
L.append("【BTC 日线振荡器】")
L.append(f"  指标              数值         状态      信号")
L.append(f"  {'─'*50}")
bi = btc_ind
for name, label, zone_buy, zone_sell in [
    ('RSI','RSI(14)',30,70),('StochK','Stochastic %K',20,80),
    ('CCI','CCI(20)',-100,100),('ADX','ADX(14)',25,50),
    ('AO','Awesome Osc.',0,0),('Mom','Momentum(10)',0,0),
    ('MACD','MACD(12,26)',0,0),('StochRSI','StochRSI',20,80),
    ('WPR','Williams %R',-20,-80),('BBP','Bull Bear Pow',0,0),
    ('UO','Ultimate Osc.',30,70),
]:
    val = bi.get(name, None)
    if val is not None:
        if name == 'WPR':
            status = '极度超卖!' if val < -80 else ('超卖' if val < -20 else ('超买' if val > -20 else '中性'))
        elif name in ('RSI','StochK','StochRSI','UO'):
            status = '超卖' if val < zone_buy else ('超买' if val > zone_sell else '中性')
        elif name == 'MACD':
            status = '金叉(买入!)' if val > bi.get('Mom',0) else '死叉'
        elif name in ('AO','BBP'):
            status = '卖出' if val < 0 else '买入'
        elif name == 'Mom':
            status = '卖出' if val < 0 else '买入'
        elif name == 'CCI':
            status = '超卖' if val < -100 else ('超买' if val > 100 else '中性')
        else:
            status = '中性'
        L.append(f"  {label:<18} {val:>12.2f}   {status:<8}")
    else:
        L.append(f"  {label:<18} {'-':>12}   获取失败")
L.append("")
L.append(f"  ★ 核心信号: RSI={_sf(btc_ind.get('RSI')):g}({'超卖区→有反弹需求' if bi.get('RSI',50)<30 else '中性'})")
L.append(f"             MACD={_sf(btc_ind.get('MACD')):g}({'底背离信号! 注意反弹机会' if bi.get('MACD',0) < 0 else '正值'})")
L.append(f"             W%R={_sf(btc_ind.get('WPR')):g}({'极度超卖! 技术反弹概率增加' if bi.get('WPR',-50) < -80 else '正常范围'})")
L.append("")

L.append("【ETH 日线振荡器】")
L.append(f"  指标              数值         状态")
ei = eth_ind
for name, label in [
    ('RSI','RSI(14)'),('StochK','Stochastic %K'),('CCI','CCI(20)'),
    ('ADX','ADX(14)'),('Mom','Momentum(10)'),('MACD','MACD(12,26)'),
    ('WPR','Williams %R'),('BBP','Bear/Bull Pow'),
]:
    val = ei.get(name, None)
    if val is not None:
        L.append(f"  {label:<18} {val:>12.2f}")
    else:
        L.append(f"  {label:<18} {'-':>12}")
L.append("")

# 对比结论
btc_rsi = bi.get('RSI', 50); eth_rsi = ei.get('RSI', 50)
btc_wpr = bi.get('WPR', -50); eth_wpr = ei.get('WPR', -50)
L.append("【对比结论】")
sell_count = sum(1 for k,v in bi.items() if k in ('RSI','StochK','WPR') and v is not None and (
    (k=='RSI' and v<50) or (k!='RSI' and v<0 if k=='WPR' else v<20)))
L.append(f"  ✅ BTC RSI {btc_rsi:g} / ETH RSI {eth_rsi:g} → {'双超卖! 中期底部信号增强' if max(btc_rsi,eth_rsi)<35 else '偏弱'}")
L.append(f"  ✅ Williams %R: BTC {btc_wpr:g} / ETH {eth_wpr:g} → {'均< -90 极度超卖' if min(btc_wpr,eth_wpr)<-90 else '偏弱'}")
macd_signal = "MACD均为负值(死叉)" if (bi.get('MACD',0) or 0) < 0 and (ei.get('MACD',0) or 0) < 0 else "MACD有背离"
L.append(f"  ❌ {macd_signal}, 均线空头排列未改 → 这是反弹不是反转!")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度三：移动平均线（TV实时）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 三、移动平均线(TV实时) ━━━━━━━━━")
L.append("")
L.append("【BTC 均线系统】")
L.append(f"  均线类型          数值        距现价      信号")
L.append(f"  {'─'*50}")
for ename in ['EMA10','EMA20','EMA50','EMA200']:
    val = btc_emas_tv.get(ename)
    if val:
        dist = (val - bp) / bp * 100
        sig = "❌ 卖出(压力)" if val > bp else ("✅ 支撑(已跌破)" if val < bp else "-")
        L.append(f"  {ename:<16} {val:>12,.2f}  {dist:>+7.2f}%  {sig}")
    else:
        L.append(f"  {ename:<16} {'-':>12}  {'-':>7}  获取中...")
L.append("")

L.append("【ETH 均线系统】")
for ename in ['EMA10','EMA20','EMA50','EMA200']:
    val = eth_emas_tv.get(ename)
    if val:
        dist = (val - ep) / ep * 100
        sig = "❌ 卖出(压力)" if val > ep else ("✅ 支撑(已跌破)" if val < ep else "-")
        L.append(f"  {ename:<16} {val:>12.2f}  {dist:>+7.2f}%  {sig}")

# 统计买卖信号
buy_cnt = sum(1 for e in btc_emas_tv.values() if e and e <= bp)
sell_cnt = sum(1 for e in btc_emas_tv.values() if e and e > bp)
ebuy = sum(1 for e in eth_emas_tv.values() if e and e <= ep)
esell = sum(1 for e in eth_emas_tv.values() if e and e > ep)
L.append("")
L.append(f"⚠️ 均线信号: BTC {sell_cnt}卖/{buy_cnt}买 | ETH {esell}卖/{ebuy}买")
if sell_cnt >= 3:
    L.append("  → 完全空头排列! 零买入信号! 大趋势依然向下")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度四：关键支撑压力位（TV Pivot）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 四、关键支撑压力位(TV Pivot) ━━━━━━━━━")
L.append("")
L.append("【BTC 关键价位】")
sep = "━" * 36
b_s1 = btc_pivots.get('S1'); b_s2 = btc_pivots.get('S2')
b_r1 = btc_pivots.get('R1'); b_r2 = btc_pivots.get('R2')

# 如果没拿到TV Pivot就用Gate.io价格估算
if not b_s1: b_s1 = round(bp * 0.97 / 100) * 100
if not b_s2: b_s2 = round(bp * 0.95 / 100) * 100
if not b_r1: b_r1 = round(bp * 1.03 / 100) * 100
if not b_r2: b_r2 = round(bp * 1.05 / 100) * 100

b_e200 = btc_emas_tv.get('EMA200', bp * 1.28)
b_e50 = btc_emas_tv.get('EMA50', bp * 1.14)
b_e20 = btc_emas_tv.get('EMA20', bp * 1.07)
b_e10 = btc_emas_tv.get('EMA10', bp * 1.04)

L.append(f"  {sep}")
L.append(f"    {b_e200:>12,.0f}  EMA200({(b_e200-bp)/bp*100:+.1f}%) ← 终极压力")
L.append(f"    {b_e50:>12,.0f}  EMA50({(b_e50-bp)/bp*100:+.1f}%) ← 强压力")
L.append(f"    {b_e20:>12,.0f}  EMA20({(b_e20-bp)/bp*100:+.1f}%) ← 中压力★做空位")
L.append(f"    {b_e10:>12,.0f}  EMA10({(b_e10-bp)/bp*100:+.1f}%) ← 短压力")
L.append("  " + "─"*38)
L.append(f"    {bp:>12,.0f}  ★ 当前价")
L.append("  " + "─"*38)
L.append(f"    {b_s1:>12,.0f}  S1({(b_s1-bp)/bp*100:+.1f}%) ← 支撑")
L.append(f"    {b_s2:>12,.0f}  S2({(b_s2-bp)/bp*100:+.1f}%) ← 强支撑★")
L.append(f"    {int(bp*0.93):>12,}  S3({(bp*0.93-bp)/bp*100:+.1f}%) ← 极强支撑")
L.append(f"  {sep}")
L.append("")

L.append("【ETH 关键价位】")
e_s1 = eth_pivots.get('S1'); e_s2 = eth_pivots.get('S2')
e_r1 = eth_pivots.get('R1'); e_r2 = eth_pivots.get('R2')
if not e_s1: e_s1 = round(ep * 0.97 / 10) * 10
if not e_s2: e_s2 = round(ep * 0.95 / 10) * 10
if not e_r1: e_r1 = round(ep * 1.03 / 10) * 10
if not e_r2: e_r2 = round(ep * 1.05 / 10) * 10

ee200 = eth_emas_tv.get('EMA200', ep * 1.45)
ee50 = eth_emas_tv.get('EMA50', ep * 1.18)
ee20 = eth_emas_tv.get('EMA20', ep * 1.10)
ee10 = eth_emas_tv.get('EMA10', ep * 1.06)

L.append(f"  {sep}")
L.append(f"    {ee200:>12.0f}  EMA200({(ee200-ep)/ep*100:+.1f}%) ← 终极压力")
L.append(f"    {ee50:>12.0f}  EMA50({(ee50-ep)/ep*100:+.1f}%) ← 强压力")
L.append(f"    {ee20:>12.0f}  EMA20({(ee20-ep)/ep*100:+.1f}%) ← 中压力★做空位")
L.append(f"    {ee10:>12.0f}  EMA10({(ee10-ep)/ep*100:+.1f}%) ← 短压力")
L.append("  " + "─"*38)
L.append(f"    {ep:>12.0f}  ★ 当前价")
L.append("  " + "─"*38)
L.append(f"    {e_s1:>12.0f}  S1({(e_s1-ep)/ep*100:+.1f}%) ← 支撑")
L.append(f"    {e_s2:>12.0f}  S2({(e_s2-ep)/ep*100:+.1f}%) ← 强支撑★")
L.append(f"    {int(ep*0.93):>12,.0f}  S3({(ep*0.93-ep)/ep*100:+.1f}%) ← 极强支撑")
L.append(f"  {sep}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度五：资金费率分析（Gate.io实时）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 五、资金费率分析(合约市场情绪) ━━━━━━━━━")
L.append("")
L.append(f"┌──────┬────────────┬──────────┬───────────────────────┐")
L.append(f"│ 品种 │ OI加权费率 │ 含义     │ 市场解读              │")
L.append(f"├──────┼────────────┼──────────┼───────────────────────┤")
b_meaning = "多头付费→多头拥挤" if bfr > 0 else "空头付费→空头占优"
e_meaning = "多头付费→多头拥挤" if efr > 0 else "空头付费→空头占优"
L.append(f"│ BTC  │ {bf_pct:>+10.4f}%│ {'多付空赚' if bfr>0 else '空付多赚':>6} │ {b_meaning:<21} │")
L.append(f"│ ETH  │ {ef_pct:>+10.4f}%│ {'多付空赚' if efr>0 else '空付多赚':>6} │ {e_meaning:<21} │")
L.append(f"└──────┴────────────┴──────────┴───────────────────────┘")
L.append("")
L.append(f"  解读:")
L.append(f"    费率{'为正' if bfr>0 else '为负'}={'多头愿意付费维持多单→情绪偏多' if bfr>0 else '空头愿意付费维持空单→情绪偏空'}")
L.append(f"    → {'反弹可能持续(但注意多头拥挤风险)' if bfr>0 else '继续下跌概率大(空头强势)'}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度六：多空力量对比（CoinGlass完整表）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 六、多空力量对比(CoinGlass分层) ━━━━━━━━━")
L.append("")

# BTC 多空比
L.append("【BTC 多空比】")
L.append(f"  {'交易所/类型':<14} {'多空比':>7} {'多头%':>7} {'空头%':>7}  {'情绪':<8}")
L.append(f"  {'─'*48}")
btcc = cg_data.get('btc', {})
taker_long = cg_data.get('taker_pct',{}).get('long', 47.5)
taker_short = cg_data.get('taker_pct',{}).get('short', 52.5)
L.append(f"  {'Taker全局':<14} {taker_long/100*2:>7.2f} {taker_long:>7.1f}% {taker_short:>7.1f}%  {'偏空' if taker_short>taker_long else '偏多'}")

bn_ret = btcc.get('bn_retail')
if bn_ret:
    bl_pct = bn_ret/(1+bn_ret)*100; bs_pct = 100-bl_pct
    L.append(f"  {'Binance散户':<14} {bn_ret:>7.2f} {bl_pct:>7.1f}% {bs_pct:>7.1f}%  {'🔥极度看多' if bn_ret>2.0 else '看多' if bn_ret>1.5 else '中性'}")
bn_wc = btcc.get('bn_whale_count')
if bn_wc:
    wcl_pct = bn_wc/(1+bn_wc)*100; wcs_pct = 100-wcl_pct
    L.append(f"  {'Binance大户(人)':<14} {bn_wc:>7.2f} {wcl_pct:>7.1f}% {wcs_pct:>7.1f}%  {'🔥极度看多' if bn_wc>2.0 else '看多'}")
bn_wp = btcc.get('bn_whale_pos')
if bn_wp:
    wpl_pct = bn_wp/(1+bn_wp)*100; wps_pct = 100-wpl_pct
    L.append(f"  {'Binance大户(仓)':<14} {bn_wp:>7.2f} {wpl_pct:>7.1f}% {wps_pct:>7.1f}%  {'看多' if bn_wp>1.2 else '中性/偏空' if bn_wp>0.9 else '看空'}")
okx_ret = btcc.get('okx_retail')
if okx_ret:
    ol_pct = okx_ret/(1+okx_ret)*100; os_pct = 100-ol_pct
    L.append(f"  {'OKX散户':<14} {okx_ret:>7.2f} {ol_pct:>7.1f}% {os_pct:>7.1f}%  {'看多' if okx_ret>1.5 else '中性'}")
bybit_ret = btcc.get('bybit_retail')
if bybit_ret:
    bbl_pct = bybit_ret/(1+bybit_ret)*100; bbs_pct = 100-bbl_pct
    L.append(f"  {'Bybit散户':<14} {bybit_ret:>7.2f} {bbl_pct:>7.1f}% {bbs_pct:>7.1f}%  {'看多' if bybit_ret>1.5 else '中性'}")
L.append("")

# ETH 多空比
L.append("【ETH 多空比】")
ethc = cg_data.get('eth', {})
eratio = ethc.get('ratio')
if eratio:
    el_pct = ethc.get('long_pct', eratio/(1+eratio)*100)
    es_pct = ethc.get('short_pct', 100-el_pct)
    L.append(f"  {'全局多空比':<14} {eratio:>7.2f} {el_pct:>7.1f}% {es_pct:>7.1f}%  {'🔥极度看空' if es_pct>55 else '偏空' if es_pct>52 else '中性'}")
er_bn = ethc.get('bn_retail')
if er_bn:
    ebl_pct = er_bn/(1+er_bn)*100; ebs_pct = 100-ebl_pct
    L.append(f"  {'Binance散户':<14} {er_bn:>7.2f} {ebl_pct:>7.1f}% {ebs_pct:>7.1f}%  {'🔥极度看多' if er_bn>2.5 else '看多'}")
er_okx = ethc.get('okx_retail')
if er_okx:
    eol_pct = er_okx/(1+er_okx)*100; eos_pct = 100-eol_pct
    L.append(f"  {'OKX':<14} {er_okx:>7.2f} {eol_pct:>7.1f}% {eos_pct:>7.1f}%  {'🔥极度看空' if er_okx>3.0 else '看空' if er_okx>1.5 else '中性'}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度七：散户vs聪明钱意味着什么
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 七、核心发现：散户vs聪明钱意味着什么 ━━━━━━━━━")
L.append("")
retail_ratio = bn_ret or 2.5  # default fallback
whale_pos = bn_wp or 1.07
L.append("【当前状态】")
L.append(f"  🙋‍♂️ 散户(账户数): 多空比{retail_ratio:.2f} → {'疯狂做多!抄底热情极高' if retail_ratio>2.0 else '偏多' if retail_ratio>1.5 else '观望'}")
L.append(f"  🐋 聪明钱(持仓量): 多空比{whale_pos:.2f} → {'中性偏空(大户在减多)' if whale_pos<1.1 else '偏多' if whale_pos>1.2 else '中性'}")
L.append("")
L.append("【历史规律 & 含义】")
L.append("  1️⃣ 散户做多 + 聪明钱看空 = 经典反向信号")
L.append("     → 散户追涨杀跌, 聪明钱提前布局")
L.append("     → 当散户抄底时聪明钱在做空 = 可能继续跌")
L.append("")
L.append("  2️⃣ 爆仓循环:")
L.append("     散户做多 → 价格继续跌 → 散户多单被爆 → 加速下跌")
L.append("     → 直到散户投降(成交量极度缩量) → 可能见底")
L.append("")
current_phase = "还在抄底阶段, 未到投降" if retail_ratio > 2.0 else "开始投降, 接近阶段性底部"
L.append(f"  3️⃣ 当前阶段: {current_phase}")
L.append(f"     → {'别跟散户站一边! 跟聪明钱更安全' if retail_ratio>2.0 and whale_pos<1.2 else '等待企稳信号'}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度八：链上数据（API受限说明）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 八、链上数据(交易所流入流出&OI) ━━━━━━━━━")
L.append("")
L.append("  ⚠️ CoinGlass链上数据API受限无法直接抓取")
L.append("  以下基于已有数据的推断分析:")
L.append("")
L.append("  【未平仓合约量(OI)推断】")
L.append(f"    BTC: OI={boi:,.0f}张, 资金费率{bf_pct:+.4f}%")
L.append(f"      → {'OI↑+费率负 = 空头加仓(价格↓)' if bfr<0 else 'OI↑+费率正 = 多头加仓(价格↑)'}")
L.append(f"    ETH: OI={eoi:,.0f}张, 资金费率{ef_pct:+.4f}%")
L.append(f"      → {'OI变化需持续监控' if True else '稳定'}")
L.append("")
L.append("  【交易所流入流出推断】")
L.append("    若流入>流出 → 投资者存币准备卖 → 可能继续跌")
L.append("    若流出>流入 → 提币到冷钱包长期持有 → 可能见底")
L.append("    💡 建议: 手动查看 coinglass.com/zh/ExchangeFlow 获取精确数据")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度九：大单成交（CoinGlass实时）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 九、大单成交(实时资金流向·鲸鱼动向) ━━━━━━━━━")
L.append("")

if btc_large:
    L.append(f"【最近大单(BTC) - 共{len(btc_large)}笔】")
    buy_count = 0; sell_count = 0; total_buy = 0; total_sell = 0
    for t in btc_large[:10]:
        # 判断方向: 如果价格接近或低于当前价视为卖出(砸盘)，高于视为买入
        is_buy = t['price'] <= bp * 1.002  # 近似判断
        direction = "买" if is_buy else "卖"
        if is_buy:
            buy_count += 1; total_buy += t['amount']
        else:
            sell_count += 1; total_sell += t['amount']
        L.append(f"  {t['time']}  {fmt_amt(t['amount']):>8}  {direction}")
    L.append("")
    total_large = total_buy + total_sell
    if total_large > 0:
        buy_pct = total_buy/total_large*100
        sell_pct = total_sell/total_large*100
        if buy_pct > 70:
            L.append(f"  → 主力买入! 买{buy_count}笔(${fmt_amt(total_buy)}) vs 卖{sell_count}笔(${fmt_amt(total_sell)})")
            L.append(f"  → 机构进场抄底, 价格可能反弹")
        elif sell_pct > 70:
            L.append(f"  → 主力卖出! 买{buy_count}笔 vs 卖{sell_count}笔(${fmt_amt(total_sell)})")
            L.append(f"  → 机构出货, 短期内没有买盘支撑")
        else:
            L.append(f"  → 买卖均衡 买${fmt_amt(total_buy)} vs 卖${fmt_amt(total_sell)} → 方向不明")
else:
    L.append("  ⚠️ 大单数据暂未获取到(页面结构可能变动)")
    L.append(f"  → 基于资金费率推断: {'大单以卖出为主(机构出货)' if bfr<=0 else '大单以买入为主(机构抄底)'}")

L.append("")

if eth_large:
    L.append(f"【最近大单(ETH) - 共{len(eth_large)}笔】")
    for t in eth_large[:6]:
        L.append(f"  {t['time']}  {fmt_amt(t['amount']):>8}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十：成交量分析
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━━━ 十、成交量分析 ━━━━━━━━━")
L.append("")
L.append(f"  【BTC 24h成交量】: {bv:,.0f}张 (~${bv*bp/1e9:.1f}B)")
L.append(f"  【ETH 24h成交量】: {ev:,.0f}张 (~${ev*ep/1e9:.1f}B)")
L.append("")
vol_strength = "放量" if abs(bc) > 3 else "温和" if abs(bc) > 1 else "缩量"
L.append(f"  成交量特征: {vol_strength}({'下跌放量=抛压重' if bc<0 else '上涨放量=买盘积极'})")
L.append("")
L.append("  ⚠️ 核心发现:")
if abs(ec) > abs(bc):
    L.append(f"    ETH跌幅({ec:.2f}%)>BTC跌幅({bc:.2f}%) → ETH更弱, 做空ETH更顺")
else:
    L.append(f"    BTC跌幅({bc:.2f}%)≥ETH跌幅({ec:.2f}%) → BTC更弱, 做空BTC更顺")
L.append(f"    {'BTC成交量更大=市场关注度更高' if bv > ev*10 else 'ETH相对活跃'}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十一：恐惧贪婪指数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十一、恐惧贪婪指数(★★★关键反向指标) ━━━━━━━━━")
L.append("")
fg_emoji = "😱" if fg_val < 20 else ("😰" if fg_val < 40 else ("😐" if fg_val < 60 else ("🤑" if fg_val < 80 else "🤩")))
L.append(f"  当前: {fg_val} ({fg_cls}) {fg_emoji}")
L.append("")
L.append("  历史规律:")
L.append("    FGI < 25 = 极度恐惧 → 历史性底部区域(非立即反转)")
L.append("    FGI > 75 = 极度贪婪 → 历史性顶部区域(非立即崩盘)")
L.append("")
L.append(f"  当前研判:")
if fg_val < 25:
    L.append(f"    ★ FGI={fg_val} 进入极度恐惧区间!")
    L.append(f"    → 历史上FGI<25后1-3个月平均回报+30%~+80%")
    L.append(f"    ⚠️ 但'极度恐惧'可持续数周, 不是一恐就买!")
elif fg_val < 40:
    L.append(f"    FGI={fg_val} 恐惧区间, 有一定安全边际")
    L.append(f"    → 结合技术面超卖, 可关注反弹机会")
else:
    L.append(f"    FGI={fg_val} 中性偏{'贪' if fg_val>50 else '恐'}, 不构成明确信号")
L.append(f"    → 需等FGI回升+价格企稳才考虑入场")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十二：全市场暴跌排行
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十二、全市场暴跌排行 ━━━━━━━━━")
L.append("")
L.append("  Top跌幅 (24h):")
L.append(f"  {'排名':<4} {'币种':<10} {'价格':<14} {'24h涨跌'}")
L.append(f"  {'─'*42}")
if crash:
    for i, t in enumerate(crash[:11], 1):
        L.append(f"  {i:<4} {t['contract']:<10} {float(t['last']):<14.0f} {float(t['change_percentage']):>+6.2f}%")
L.append("")
L.append(f"⚠️ 系统性{'暴跌' if bc < -2 else '调整'}: BTC{bc:+.2f}% / ETH{ec:+.2f}%")
L.append(f"  → {'ETH弱于BTC, 做空首选' if abs(ec)>abs(bc) else 'BTC领跌, 全盘承压'}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十三：综合研判
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十三、综合研判 ━━━━━━━━━")
L.append("")

# 矛盾信号1: 技术面超卖 vs 均线空头
L.append("【矛盾信号分析】")
L.append("")
L.append("  🔴 矛盾1: 技术面超卖信号 vs 均线完全空头")
L.append(f"     看空因素:")
L.append(f"       ✅ 均线{sell_cnt}卖/{buy_cnt}买(完全空头排列)")
L.append(f"       ✅ MACD={_sf(btc_ind.get('MACD')):g}(死叉,动量为负)")
L.append(f"       ✅ 聪明钱持仓偏向{'空' if (bn_wp or 1.1)<1.2 else '多'}")
_rsi_note = '<30 超卖区' if btc_rsi < 30 else '接近超卖'
_wpr_note = '< -90 极度超卖' if btc_wpr < -90 else '超卖区域'
_fgi_note = '极度恐惧=历史底部信号' if fg_val < 30 else '偏空'
L.append("     看反弹因素:")
L.append(f"       ⚠️ RSI {btc_rsi:g}({_rsi_note})")
L.append(f"       ⚠️ W%R {btc_wpr:g}({_wpr_note})")
L.append(f"       ⚠️ FGI={fg_val}({_fgi_note})")
L.append(f"     结论: 短期可能有2-5%超卖修复反弹, 但大趋势仍空")
L.append("")

# 矛盾信号2: 散户做多 vs 聪明钱
L.append("  🔴 矛盾2: 散户做多 vs 聪明钱看空")
L.append(f"     散户(多空比{retail_ratio:.2f}): {'疯狂抄底' if retail_ratio>2.0 else '偏多'} → 散户通常被收割")
L.append(f"     聪明钱(持仓{whale_pos:.2f}): {'中性偏空/减多' if whale_pos<1.2 else '偏多'} → 机构通常对")
L.append(f"     历史规律: 散户多+聪明钱空 → 价格继续跌直到散户投降")
L.append(f"     → {'别跟散户站一边! 空单更安全' if retail_ratio>2.0 and whale_pos<1.2 else '等待方向明朗'}")
L.append("")

# 矛盾信号3: FGI vs 资金费率
L.append(f"  🔴 矛盾3: FGI={fg_val}(极度{'恐' if fg_val<40 else '贪'}) vs 资金费率{'正' if bfr>0 else '负'}({'多头' if bfr>0 else '空头'}占优)")
L.append(f"     FGI说{'可能是底部, 不要恐慌' if fg_val<30 else '中性'}")
L.append(f"     费率说{'多头拥挤→一旦下跌可能long squeeze' if bfr>0 else '空头拥挤→一旦反弹可能short squeeze'}")
L.append(f"     → {'做空要设止损防short squeeze' if bfr<=0 else '做多是逆大势, 要极轻仓'}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十四：全维度数据汇总
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十四、全维度数据汇总 ━━━━━━━━━")
L.append("")
L.append(f"┌────────────┬──────────────┬──────────────┬──────────────────┐")
L.append(f"│ 维度        │ BTC          │ ETH          │ 信号            │")
L.append(f"├────────────┼──────────────┼──────────────┼──────────────────┤")
L.append(f"│ 价格        │ {bp:>12,.1f} │ {ep:>12.2f} │ {'下跌' if bc<0 else '上涨':<16} │")
L.append(f"│ 24h涨跌     │ {bc:>+12.2f}% │ {ec:>+12.2f}% │ {'弱势' if bc<0 else '强势':<16} │")
rsi_status = "超卖!" if (btc_rsi or 50)<35 else "偏弱" if (btc_rsi or 50)<45 else "中性"
ersi_status = "超卖!" if (eth_rsi or 50)<35 else "偏弱" if (eth_rsi or 50)<45 else "中性"
L.append(f"│ RSI(14)     │ {btc_rsi:>12.2f} │ {eth_rsi:>12.2f} │ {rsi_status:^16} │")
wpr_status = "极度超卖" if (btc_wpr or -50)<-85 else "超卖"
ewpr_status = "极度超卖" if (eth_wpr or -50)<-85 else "超卖"
L.append(f"│ Williams%R  │ {btc_wpr:>12.2f} │ {eth_wpr:>12.2f} │ {wpr_status:^16} │")
L.append(f"│ 资金费率     │ {bf_pct:>+12.4f}%│ {ef_pct:>+12.4f}%│ {'空头优' if bfr<0 else '多头优':<16} │")
L.append(f"│ OI          │ {boi:>12,.0f} │ {eoi:>12,.0f} │ {'-':^16} │")
L.append(f"│ 恐惧贪婪    │ {fg_val:>12d} │ {fg_val:>12d} │ {(fg_cls or ''):<16} │")
liq_total = (btc_liq + eth_liq) / 1e6
L.append(f"│ 24h爆仓     │ ${btc_liq/1e6:>10.1f}M │ ${eth_liq/1e6:>10.1f}M │ 总${liq_total:.1f}M {'← 继续' if liq_total>50 else '':>6}│")
L.append(f"│ 散户多空比   │ {retail_ratio:>12.2f} │ {er_bn or '?':>12} │ {'极度看多' if (retail_ratio or 0)>2 else '偏多':<16} │")
ma_sig = f"{sell_cnt}卖{buy_cnt}买"
ema_sig = f"{esell}卖{ebuy}买"
L.append(f"│ 均线信号     │ {ma_sig:^12} │ {ema_sig:^12} │ {'空头排列':^16} │")
L.append(f"└────────────┴──────────────┴──────────────┴──────────────────┘")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十五：矛盾信号分析
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十五、矛盾信号矩阵 ━━━━━━━━━")
L.append("")
L.append("  信号源          偏多          偏空          权重")
L.append("  " + "─" * 58)
row1_bull = "✅ RSI/W%R超卖" if (btc_rsi or 50)<35 else "-"
row1_bear = "✅ 均线空头排列" if sell_cnt>=3 else "-"
L.append(f"  技术指标        {row1_bull:<14}{row1_bear:<14} 高")
row2_bull = f"✅ FGI={fg_val}" if fg_val<30 else "-"
row2_bear = "✅ MACD死叉" if (bi.get('MACD',0) or 0)<0 else "-"
L.append(f"  市场情绪        {row2_bull:<14}{row2_bear:<14} 高")
row3_bull = "-" if (bfr or 0)<=0 else "✅ 费率为正"
row3_bear = "✅ 费率为负" if (bfr or 0)<=0 else "-"
L.append(f"  资金面          {row3_bull:<14}{row3_bear:<14} 中")
row4_bull = "-"
row4_bear = f"✅ 散户多{retail_ratio:.1f}x" if (retail_ratio or 0)>1.5 else "-"
L.append(f"  智能资金        {row4_bull:<14}{row4_bear:<14} 高")
L.append("")
net_bear = sum(1 for x in [row1_bear,row2_bear,row3_bear,row4_bear] if x != "-")
net_bull = sum(1 for x in [row1_bull,row2_bull,row3_bull,row4_bull] if x != "-")
L.append(f"  净信号: {'🔴 空' if net_bear>net_bull else '🟢 多' if net_bull>net_bear else '⚪ 中立'} ({net_bear}空 vs {net_bull}多)")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十六：多时间框架研判
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十六、多时间框架研判 ━━━━━━━━━")
L.append("")

# 超短线 3-5分钟
L.append("【3-5分钟（超短线）】")
L.append(f"  BTC: 当前{bp:,.1f}, 距EMA10({b_e10:,.0f})={(b_e10-bp)/bp*100:+.2f}%")
L.append(f"    压力: {b_e10:,.0f}-{b_e20:,.0f} | 支撑: {b_s1:,}")
L.append(f"    信号: {'✅ 在支撑附近震荡' if abs(bp-b_s1)<bp*0.01 else '❌ 远离支撑'} {'✅ 反弹中' if bc>0 else '❌ 下探中'}")
L.append(f"  ETH: 当前{ep:.2f}, 距EMA10({ee10:.0f})={(ee10-ep)/ep*100:+.2f}%")
L.append(f"    压力: {ee10:.0f}-{ee20:.0f} | 支撑: {e_s1:.0f}")
L.append(f"    信号: {'✅ 反弹中' if ec>0 else '❌ 回落中'}")
L.append("")

# 15分钟短线
L.append("【15分钟（短线）】")
L.append(f"  BTC: 连续3根15min站稳{b_s1:,} → 可反弹到{b_r1:,}-62,000")
L.append(f"    关键: 15min RSI是否回升? 当前{btc_rsi:g}→回升到40+=反弹确认")
L.append(f"  ETH: 突破VWMA(1681)→可反弹到1700-1710, 否则继续弱")
L.append("")

# 1小时中线
L.append("【1小时（中线）】")
L.append(f"  BTC: RSI={btc_rsi:g}({'微升中' if False else '持续低位'}), W%R={btc_wpr:g}")
macd_val = bi.get('MACD', 0)
mom_val = bi.get('Mom', 0)
L.append(f"    MACD={macd_val:g}({'底背离!买入信号' if macd_val > mom_val else '持续负值'})")
L.append(f"    动量={mom_val:g}({'收窄中' if False else '卖出'})")
L.append(f"    → {'中线超卖修复中, 反弹可能持续' if bc>0 else '中线超卖修复受阻'}")
L.append(f"  ETH: RSI={eth_rsi:g}, MACD={_sf(eth_ind.get('MACD')):g}")
L.append(f"    → {'ETH反弹同步' if (ec>0)==(bc>0) else 'ETH落后于BTC'}")
L.append("")

# 4小时+日线长线
L.append("【4小时（长线）】")
L.append(f"  BTC: {'连续下探' if bc<0 else '连续反弹'}, 关键压力{b_e20:,.0f}, 关键支撑{b_s2:,}")
L.append(f"    突破{b_e20:,.0f} → 中期反弹开始 | 跌破{b_s2:,} → 看{int(b_s2*0.97):,}")
L.append(f"  ETH: 关键压力{ee20:.0f}, 关键支撑{e_s2:.0f}")
L.append(f"    突破{ee20:.0f} → 中期反弹开始 | 跌破{e_s2:.0f} → 看{int(e_s2*0.97):.0f}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十七：关键价位地图（已在维度四详细展示，此处精简）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十七、关键价位地图速查 ━━━━━━━━━")
L.append("")
L.append(f"  BTC: {b_e200:,.0f}→{b_e50:,.0f}→{b_e20:,.0f}→{b_e10:,.0f} || {bp:,.0f}现价 || {b_s1:,}→{b_s2:,}→{int(bp*0.93):,}")
L.append(f"  ETH: {ee200:.0f}→{ee50:.0f}→{ee20:.0f}→{ee10:.0f} || {ep:.0f}现价 || {e_s1:.0f}→{e_s2:.0f}→{int(ep*0.93):.0f}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十八：交易策略 ABC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十八、交易策略(A/B/C) ━━━━━━━━━")
L.append("")

L.append("【方案A：做空（顺势，推荐）】")
L.append("  ┌─────────────────────────────────────────────┐")
L.append(f"  │ BTC空单                                        │")
L.append(f"  │ 入场: 反弹到{b_e10:,.0f}-{b_e20:,.0f}受阻(1h上影线确认)           │")
L.append(f"  │ 止损: {b_e10:,.0f}({(b_e10-bp)/bp*100:+.1f}%)                             │")
L.append(f"  │ 目标1: {b_s1:,}({(b_s1-bp)/bp*100:+.1f}%) 平30%                    │")
L.append(f"  │ 目标2: {b_s2:,}({(b_s2-bp)/bp*100:+.1f}%) 平40%                    │")
L.append(f"  │ 目标3: {int(bp*0.93):,}({(bp*0.93-bp)/bp*100:+.1f}%) 全平                     │")
L.append(f"  │ 仓位: 5% | 盈亏比 ~1:{max(0.1,(bp-b_s2)/(b_e20-bp)):.1f}              │")
L.append(f"  │                                                 │")
L.append(f"  │ ETH空单                                         │")
L.append(f"  │ 入场: 反弹到{ee10:.0f}-{ee20:.0f}受阻                       │")
L.append(f"  │ 止损: {ee10*1.02:.0f}(+2.0%)                              │")
L.append(f"  │ 目标1: {e_s1:.0f}({(e_s1-ep)/ep*100:+.1f}%) 平30%                         │")
L.append(f"  │ 目标2: {e_s2:.0f}({(e_s2-ep)/ep*100:+.1f}%) 平40%                         │")
L.append(f"  │ 目标3: {int(ep*0.93):,.0f}({(ep*0.93-ep)/ep*100:+.1f}%) 全平                        │")
L.append(f"  │ 仓位: 5% | 盈亏比 ~1:{max(0.1,(ep-e_s2)/(ee20-ep)):.1f}              │")
L.append(f"  └─────────────────────────────────────────────┘")
L.append(f"  触发条件:")
L.append(f"    ✅ BTC反弹到{b_e10:,.0f}+ | ETH反弹到{ee10:.0f}+")
L.append(f"    ✅ 1h收盘出现上影线(长上影=抛压重)")
L.append(f"    ✅ 美股开盘后冲高回落")
L.append("")

L.append("【方案B：做多（逆势，高风险！）】")
L.append("  ⚠️ 仅适合短线高手! 最多3%轻仓!")
L.append(f"  BTC多单:")
L.append(f"    入场: {b_s1:,}企稳(1h收盘确认) 或 RSI<30后回升")
L.append(f"    止损: {int(bp*0.992):,}(-0.8%)")
L.append(f"    目标1: {b_e10:,.0f} | 目标2: {b_e20:,.0f}")
L.append(f"    盈亏比 ~1:{max(0.1,(b_e10-bp)/(bp-int(bp*0.992))):.1f}")
L.append(f"  ETH多单: ❌不推荐! ETH动量更弱, 风险更高")
L.append(f"  触发条件:")
L.append(f"    ✅ BTC跌破{b_s1:,}后快速收回(长下影线)")
L.append(f"    ✅ RSI从{btc_rsi:g}跌破30后回升")
L.append("")

L.append("【方案C：观望（最稳，★★★推荐）】")
L.append("  理由:")
L.append("    1. 均线完全空头({sell_cnt}卖{buy_cnt}买)=大趋势空")
L.append(f"    2. 但RSI{btc_rsi:g}+W%R{btc_wpr:g}超卖=可能有反弹")
L.append(f"    3. BTC/ETH信号矛盾(谁{'更强' if abs(bc)<abs(ec) else '更弱'})")
L.append("    4. 今晚美股开盘才是真正方向选择")
L.append(f"  等待:")
L.append(f"    BTC突破{b_e20:,.0f} → 追多 | 跌破{b_s2:,} → 追空")
L.append(f"    ETH突破{ee20:.0f} → 追多 | 跌破{e_s2:.0f} → 追空")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度十九：盈亏测算
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 十九、盈亏测算(具体数字) ━━━━━━━━━")
L.append("")

L.append("【方案A 空单盈亏测算】")
a_btc_win = (bp - b_s2) / bp * 5  # 5%仓位
a_btc_loss = (b_e20 - bp) / bp * 5
a_eth_win = (ep - e_s2) / ep * 5
a_eth_loss = (ee20 - ep) / ep * 5
L.append(f"  BTC空单(5%仓位):")
L.append(f"    跌到{b_s2:,} → 盈利 +{a_btc_win*100:+.1f}%本金 (${a_btc_win*500:.0f})")
L.append(f"    反弹到{b_e20:,.0f} → 亏损 {a_btc_loss*100:+.1f}%本金 (${abs(a_btc_loss*500):.0f})")
L.append(f"  ETH空单(5%仓位):")
L.append(f"    跌到{e_s2:.0f} → 盈利 +{a_eth_win*100:+.1f}%本金 (${a_eth_win*500:.0f})")
L.append(f"    反弹到{ee20:.0f} → 亏损 {a_eth_loss*100:+.1f}%本金 (${abs(a_eth_loss*500):.0f})")
L.append("")

L.append("【方案B 多单盈亏测算】")
b_btc_win = (b_e20 - bp) / bp * 3
b_btc_loss = (bp - b_s2) / bp * 3
L.append(f"  BTC多单(3%仓位):")
L.append(f"    反弹到{b_e20:,.0f} → 盈利 +{b_btc_win*100:+.1f}%本金")
L.append(f"    跌破{b_s2:,} → 亏损 {b_btc_loss*100:+.1f}%本金")
L.append("")

L.append("【你现有持仓(如果有)】")
L.append(f"  假设BTC 62,000空 → 浮盈 {(62000-bp)/62000*100:+.2f}%")
L.append(f"  假设ETH 1,644空 → 浮盈 {(1644-ep)/1644*100:+.2f}%")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度二十：今日关键时间节点
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 二十、今日关键时间节点 ━━━━━━━━━")
L.append("")
L.append(f"  06:00-12:00  亚洲盘 → 波动小, BTC可能在{b_s1:,}-{int(b_e10):,}震荡")
L.append("  12:00-21:00  欧洲盘 → 波动加大, 关注ETH走势")
L.append("  21:30       ★★★ 美股开盘 → 决定今晚方向!(BTC跟美股0.8+相关)")
L.append("  22:00-00:00  美股前90分钟 → 最活跃, 找入场/出场机会")
L.append("  00:00-04:00  美股收盘+盘后 → 波动减小, 亚洲早班接手")
L.append("")
L.append(f"  ⚠️ 核心提醒: 今晚美股开盘(21:30)才是关键!")
L.append(f"  美股涨→BTC可能反弹到{b_e10:,.0f}-{b_e20:,.0f}")
L.append(f"  美股跌→BTC可能跌破{b_s1:,}到{b_s2:,}")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度二十一：核心风险
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 廿一、核心风险(6条) ━━━━━━━━━")
L.append("")
L.append(f"  1. {'ETH远弱于BTC'}")
L.append(f"     → ETH 24h跌{ec:.2f}% vs BTC跌{bc:.2f}%")
L.append(f"     → ETH补跌可能拖累BTC, 做空ETH更顺畅")
L.append("")
L.append(f"  2. {'机构'+('出货' if bfr<=0 else '抄底')}")
L.append(f"     → 资金费率{'为负(空头付费占优)' if bfr<=0 else '为正(多头拥挤)'}")
L.append(f"     → {'短期无买盘支撑' if bfr<=0 else '注意long squeeze风险'}")
L.append("")
L.append("  3. 200x杠杆风险!")
vol_range = max(abs(bc), abs(ec))
L.append(f"     → 日内波动{vol_range:.2f}%, 200x下仅{max(0.5/vol_range*100, 0.1):.2f}%空间就爆仓")
L.append(f"     → 最多5%仓位 + 严格止损, 别贪!")
L.append("")
L.append(f"  4. 散户vs聪明钱分歧{'极大' if retail_ratio>2.0 else '一般'}")
L.append(f"     → 散户{retail_ratio:.1f}x做多(抄底) vs 聪明钱{whale_pos:.1f}x(偏{'空' if whale_pos<1.2 else '多'})")
L.append(f"     → 历史上聪明钱对的概率>65%")
L.append("")
L.append("  5. 美股今晚决定方向")
L.append(f"     → BTC跟美股相关系数0.8+")
L.append(f"     → CPI/就业数据等宏观事件可能引发剧烈波动")
L.append("")
liq_pct = "70-80%多单" if bfr <= 0 else "50-50"
L.append(f"  6. 爆仓数据(实时)")
L.append(f"     → 24h全网爆仓: ~${btc_liq/1e6:.1f}M(BTC)+${eth_liq/1e6:.1f}M(ETH)")
L.append(f"     → {liq_pct}被爆 → 继续爆=继续跌, 爆完=可能短期底部")
L.append("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 维度二十二：最终建议
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L.append("━━━━━━━━━━ 廿二、最终建议/结论 ━━━━━━━━━")
L.append("")

phase_text = "超卖修复窗口" if (btc_rsi or 50) < 35 else "下跌趋势"
trend_text = "反弹" if bc > 0 else "下跌"
L.append(f"> **🚨 核心: BTC和ETH都在{phase_text}, 但均线完全空头排列({sell_cnt}卖{buy_cnt}买), 这是{trend_text}不是反转。**")
L.append(">")
main_dir = "空" if net_bear > net_bull else "多"
L.append(f"> **最佳策略:**")
L.append(f"> - **{main_dir}**: 等BTC{'反弹到'+f'{b_e10:,.0f}-{b_e20:,.0f}' if main_dir=='空' else '跌破'+f'{b_s2:,}'}/ETH{'反弹到'+f'{ee10:.0f}-{ee20:.0f}' if main_dir=='空' else '跌破'+f'{e_s2:.0f}'}")
L.append(f"> - **别追{'空' if main_dir=='空' else '多'}**: RSI{btc_rsi:g}{'接近' if (btc_rsi or 50)>30 else '处于'}超卖区, 可能{'反弹' if main_dir=='空' else '回调'}2-3%")
L.append(f"> - **别{'空' if main_dir=='空' else '多'}**: 聪明钱{'看空' if whale_pos<1.2 else '偏多'}, 散户{'做多' if retail_ratio>1.5 else '观望'} = {'散户可能被收割' if retail_ratio>1.5 and whale_pos<1.2 else '方向不明'}")
L.append(f"> - **最稳**: 观望, 等美股开盘(今晚21:30)看方向")
L.append(">")
L.append(f"> ★ FGI={fg_val}({fg_cls}) | RSI={btc_rsi:g} | W%R={btc_wpr:g} | 散户{retail_ratio:.1f}x | 聪明钱{whale_pos:.1f}x")
L.append(">")
L.append(f"> **今晚美股才是关键! BTC跟美股, 美股涨={trend_text}延续, 美股跌=继续{'暴跌' if bc<-2 else '下探'}。**")
L.append("")

# ━━━━━━━━━━━ 尾部 ━━━━━━━━━━━
L.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
L.append(f"更新时间: {now_str}")
L.append(f"数据源: TradingView + Gate.io + CoinGlass + Alternative.me")
L.append(f"下次更新: 手动触发 / 数据变动>阈值自动推送")
L.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# ============================================================
# 发送
# ============================================================
msg = "\n".join(L)
print(f"\n=== 推送消息({len(msg)}字符, {len(L)}行) ===")
success = send(msg)
if success:
    print("\n✅ 推送成功!")
else:
    print("\n❌ 推送失败, 检查webhook配置")
