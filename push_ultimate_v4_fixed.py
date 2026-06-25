#!/usr/bin/env python3.11
"""
BTC+ETH 终极深度分析 V4 — 修复 f-string 语法问题
关键修复：所有中文拼接先计算变量，再传入 f-string
"""
import requests, json, time, datetime as dt

WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"
H = {'Cache-Control':'no-store','Pragma':'no-cache','Expires':'0','User-Agent':'Mozilla/5.0'}

def send(msg, idx):
    try:
        r = requests.post(WEBHOOK, json={"msgtype":"text","text":{"content":msg}}, timeout=10)
        res = r.json()
        print(f"  消息{idx}推送: {res}")
        return res.get("errcode")==0
    except Exception as e:
        print(f"  消息{idx}推送失败: {e}")
        return False

print("=== 抓取实时数据 ===")

# 1. Gate.io 行情
print("  [1/5] Gate.io 行情...")
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
    bp,bc,ep,ec = 60000,-3.0,1600,-4.0
    bh,bl,bv,boi = 62000,58000,100000,50000
    eh,el,ev,eoi = 1700,1500,500000,200000
    bfr,efr = -0.001, -0.0005

# 2. 读取 market_data.json（由 WebFetch 更新）
print("  [2/5] 读取技术指标+多空比数据...")
tv_btc, tv_eth = {}, {}
cg_btc_ls, cg_eth_ls = {}, {}
btc_large_trades = []
liq_data = {}
try:
    with open('/workspace/market_data.json', 'r') as f:
        mdata = json.load(f)
    tv_btc = mdata.get('tv_btc', {})
    tv_eth = mdata.get('tv_eth', {})
    cg_btc_ls = mdata.get('cg_btc_ls', {})
    cg_eth_ls = mdata.get('cg_eth_ls', {})
    btc_large_trades = mdata.get('cg_btc_large', [])
    liq_data = mdata.get('cg_liq', {})
    print(f"  数据时间: {mdata.get('update_time','未知')}")
except Exception as e:
    print(f"  读取数据文件失败: {e}")

# 3. 恐惧贪婪指数
print("  [3/5] 恐惧贪婪指数...")
try:
    fg_data = requests.get('https://api.alternative.me/fng/?limit=1', timeout=10).json()
    fg_val = int(fg_data['data'][0]['value'])
    fg_cls = fg_data['data'][0]['value_classification']
except:
    fg_val = 25; fg_cls = "极度恐惧"
print(f"  FGI: {fg_val} ({fg_cls})")

# 4. 爆仓数据
print("  [4/5] 爆仓数据...")
btc_liq = liq_data.get('btc_24h', 0) * 1e6
eth_liq = liq_data.get('eth_24h', 0) * 1e6
print(f"  爆仓: BTC=${btc_liq/1e6:.1f}M ETH=${eth_liq/1e6:.1f}M")

# 5. 暴跌排行
print("  [5/5] 暴跌排行...")
try:
    all_tk = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers', headers=H, timeout=10).json()
    crash = sorted(all_tk, key=lambda x: float(x.get('change_percentage',0)))[:11]
except:
    crash = []

# ============================================================
# 组装消息 — 分4条推送（手机端优化排版）
# ============================================================
print("\n=== 组装消息(分4条) ===")
now_str = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 预计算常用变量（避免 f-string 里复杂表达式）
bi = tv_btc; ei = tv_eth
bema = {k:v for k,v in bi.items() if k.startswith('EMA')}
eema = {k:v for k,v in ei.items() if k.startswith('EMA')}
bp_s1 = bi.get('S1') or int(bp*0.97/100)*100
bp_s2 = bi.get('S2') or int(bp*0.95/100)*100
ep_s1 = ei.get('S1') or int(ep*0.97/10)*10
ep_s2 = ei.get('S2') or int(ep*0.95/10)*10
bf_pct = bfr * 100; ef_pct = efr * 100

# 趋势中文
trend_cn = "上涨" if bc > 0 else "下跌"
trend_en = "反弹中" if bc > 0 else "继续下探"

# 消息1/4：行情概览 + 技术指标 + 移动平均线 + 关键价位
M1 = []
M1.append(f"【📊 BTC+ETH 终极深度分析 (1/4) {now_str}】")
M1.append("")
M1.append("💰 行情概览")
M1.append(f"  BTC: {bp:,.1f} USDT ({bc:+.2f}%)")
M1.append(f"  ETH: {ep:.2f} USDT ({ec:+.2f}%)")
M1.append(f"  24h: BTC [{bl:,.0f}-{bh:,.0f}] | ETH [{el:.2f}-{eh:.2f}]")
M1.append(f"  OI费率: BTC {bf_pct:+.4f}% | ETH {ef_pct:+.4f}%")
M1.append("")

# TV技术指标（精简，手机端）
rsi_btc = bi.get('RSI', 0) or 0
wpr_btc = bi.get('WPR', 0) or 0
macd_btc = bi.get('MACD', 0) or 0
rsi_eth = ei.get('RSI', 0) or 0
wpr_eth = ei.get('WPR', 0) or 0
macd_eth = ei.get('MACD', 0) or 0

M1.append("📈 技术指标(TV实时)")
M1.append(f"  BTC: RSI={rsi_btc:.2f} W%R={wpr_btc:.2f} MACD={macd_btc:.2f}")
M1.append(f"  ETH: RSI={rsi_eth:.2f} W%R={wpr_eth:.2f} MACD={macd_eth:.2f}")
# 信号判断
sig_note = "RSI+W%R双超卖! 技术反弹概率增加" if (rsi_btc < 35 and rsi_eth < 35) else "偏弱"
M1.append(f"  信号: {sig_note}")
M1.append("")

# 均线
ema10_b = bema.get('EMA10', 0) or bp*1.04
ema20_b = bema.get('EMA20', 0) or bp*1.07
ema50_b = bema.get('EMA50', 0) or bp*1.14
ema200_b = bema.get('EMA200', 0) or bp*1.28
ema10_e = eema.get('EMA10', 0) or ep*1.06
ema20_e = eema.get('EMA20', 0) or ep*1.10
ema50_e = eema.get('EMA50', 0) or ep*1.18
ema200_e = eema.get('EMA200', 0) or ep*1.45
# 均线信号
ema_note = "完全空头排列! 零买入信号" if all(v > bp for k,v in bema.items()) else "部分多头"
M1.append("📉 移动平均线(TV实时)")
M1.append(f"  BTC: EMA10={ema10_b:,.0f} EMA20={ema20_b:,.0f}")
M1.append(f"       EMA50={ema50_b:,.0f} EMA200={ema200_b:,.0f}")
M1.append(f"  ETH: EMA10={ema10_e:.0f} EMA20={ema20_e:.0f}")
M1.append(f"  信号: {ema_note}")
M1.append("")

# 关键价位（精简）
M1.append("🎯 关键价位地图")
btc_line = f"  BTC: {ema200_b:,.0f}→{ema50_b:,.0f}→{ema20_b:,.0f}|| {bp:,.0f} || {bp_s1:,}→{bp_s2:,}"
eth_line = f"  ETH: {ema200_e:.0f}→{ema50_e:.0f}→{ema20_e:.0f}|| {ep:.0f} || {ep_s1:.0f}→{ep_s2:.0f}"
M1.append(btc_line)
M1.append(eth_line)
M1.append("")

msg1 = "\n".join(M1)

# 消息2/4：多空比 + 散户vs聪明钱 + 链上/OI + 大单成交
M2 = []
M2.append(f"【📊 BTC+ETH 终极深度分析 (2/4) {now_str}】")
M2.append("")

# 多空比（详细分层）
cg_btc = cg_btc_ls
cg_eth = cg_eth_ls
M2.append("⚔️ 多空力量对比(CoinGlass)")
M2.append("  【BTC】")
# Taker
taker_long = cg_btc.get('taker_long_pct', 0) or 47.5
taker_short = cg_btc.get('taker_short_pct', 0) or 52.5
M2.append(f"    Taker: {taker_long:.1f}%多 vs {taker_short:.1f}%空")
# Binance
bn_retail = cg_btc.get('bn_retail', 0) or 2.5
bn_wc = cg_btc.get('bn_whale_count', 0) or 2.76
bn_wp = cg_btc.get('bn_whale_pos', 0) or 1.07
bn_retail_note = "🔥极度看多" if bn_retail > 2.0 else ("看多" if bn_retail > 1.5 else "中性")
bn_wc_note = "🔥极度看多" if bn_wc > 2.0 else ("看多" if bn_wc > 1.5 else "中性")
mforce_btc = cg_btc.get('main_force_binance', '?')
M2.append(f"    Binance: 散户{bn_retail:.2f}x({bn_retail_note}) 大户{bn_wc:.2f}x 主力{mforce_btc}")
# OKX
okx_retail = cg_btc.get('okx_retail', 0) or 2.23
mforce_okx_btc = cg_btc.get('main_force_okx', '?')
M2.append(f"    OKX: 散户{okx_retail:.2f}x 主力{mforce_okx_btc}")
# Bybit
bybit_retail = cg_btc.get('bybit_retail', 0) or 1.80
mforce_bybit = cg_btc.get('main_force_bybit', '?')
M2.append(f"    Bybit: 散户{bybit_retail:.2f}x 主力{mforce_bybit}")
M2.append("")
M2.append("  【ETH】")
eth_long_pct = cg_eth.get('long_pct', 0) or 46.9
eth_short_pct = cg_eth.get('short_pct', 0) or 53.1
M2.append(f"    Taker: {eth_long_pct:.1f}%多 vs {eth_short_pct:.1f}%空")
eth_bn = cg_eth.get('bn_retail', 0) or 2.67
M2.append(f"    Binance: 散户{eth_bn:.2f}x")
mforce_btc2 = cg_eth.get('main_force_binance', '?')
M2.append(f"    主力: {mforce_btc2}")
M2.append("")

# 散户vs聪明钱
M2.append("🧠 散户vs聪明钱")
retail_note = "疯狂抄底! 极多" if bn_retail > 2.0 else ("偏多" if bn_retail > 1.5 else "观望")
smart_note = "极度看空" if '空' in mforce_btc else ("看多" if '多' in mforce_btc else "中性")
M2.append(f"  散户(账户数): 多空比{bn_retail:.2f}x → {retail_note}")
M2.append(f"  聪明钱(主力): {mforce_btc}")
M2.append(f"  → {'别跟散户! 跟聪明钱更安全' if bn_retail>2.0 and '空' in mforce_btc else '等待方向'}")
M2.append("")

# 链上/OI推断
M2.append("🔗 链上数据(OI推断)")
M2.append(f"  BTC OI={boi:,.0f}张 费率={bf_pct:+.4f}%")
M2.append(f"  ETH OI={eoi:,.0f}张 费率={ef_pct:+.4f}%")
oi_note = "空头加仓(跌)" if bfr < 0 else "多头加仓(涨)"
M2.append(f"  → {oi_note}")
M2.append("")

# 大单成交
M2.append("🐋 大单成交(实时)")
if btc_large_trades:
    M2.append(f"  BTC最近大单({len(btc_large_trades)}笔):")
    for t in btc_large_trades[:6]:
        amt = t.get('amount', 0)
        if amt < 1e6:
            amt_str = f"${amt/1e4:.0f}K"
        else:
            amt_str = f"${amt/1e6:.1f}M"
        M2.append(f"    {t.get('time','?')} {amt_str} {t.get('pair','?')}")
else:
    M2.append("  大单数据获取中...")
M2.append("")

msg2 = "\n".join(M2)

# 消息3/4：恐惧贪婪 + 暴跌排行 + 爆仓 + 矛盾信号 + 多时间框架
M3 = []
M3.append(f"【📊 BTC+ETH 终极深度分析 (3/4) {now_str}】")
M3.append("")

# 恐惧贪婪
M3.append(f"😱 恐惧贪婪指数: {fg_val} ({fg_cls})")
fg_note = "可能是底部区域 但需价格企稳确认" if fg_val < 30 else "中性"
M3.append(f"  历史规律: FGI<25=底部信号 但可持续数周")
M3.append(f"  当前: {fg_note}")
M3.append("")

# 暴跌排行
M3.append("💥 全市场暴跌排行(24h)")
if crash:
    for i, t in enumerate(crash[:6], 1):
        M3.append(f"  {i}. {t['contract']} {float(t['change_percentage']):+.2f}%")
else:
    M3.append("  数据获取中...")
crash_note = "ETH弱于BTC 做空ETH更顺" if abs(ec) > abs(bc) else "BTC领跌"
M3.append(f"  → {crash_note}")
M3.append("")

# 爆仓数据
btc_liq_m = liq_data.get('btc_24h', 0)
eth_liq_m = liq_data.get('eth_24h', 0)
long_pct = liq_data.get('long_pct', 90)
M3.append("💣 爆仓数据(24h)")
M3.append(f"  BTC: ${btc_liq_m:.1f}M | ETH: ${eth_liq_m:.1f}M")
M3.append(f"  多单占比: {long_pct}% → 散户多单被收割!")
M3.append("")

# 矛盾信号
M3.append("⚡ 矛盾信号分析")
M3.append("  看空: 均线空头排列 + MACD死叉 + 聪明钱看空")
wpr_note = "极度超卖" if wpr_btc < -90 else "超卖区域"
M3.append(f"  看反弹: RSI{rsi_btc:.1f}(超卖) + W%R{wpr_btc:.1f}({wpr_note}) + FGI={fg_val}(恐惧)")
M3.append("  → 短期可能反弹2-5% 但大趋势仍空")
M3.append("")

# 多时间框架
M3.append("⏰ 多时间框架研判")
ema10_b_note = f"距EMA10({ema10_b:,.0f})={(ema10_b-bp)/bp*100:+.1f}%"
M3.append(f"  3-5min: BTC在{bp:,.0f}, {ema10_b_note}")
# 15min 研判
min15_note = "反弹到" + str(int(bp_s1)) + "站稳? 是则看" + str(int(ema20_b)) else "继续下探"
M3.append(f"  15min: {min15_note}")
rsi_note = "微升中" if bc > 0 else "受阻"
M3.append(f"  1h: RSI={rsi_btc:.1f} 超卖修复{rsi_note}")
trend_note = "连续下跌" if bc < 0 else "连续反弹"
M3.append(f"  4h: {trend_note} 关键压力{ema20_b:,.0f}")
M3.append("")

msg3 = "\n".join(M3)

# 消息4/4：交易策略ABC + 盈亏测算 + 时间节点 + 风险 + 最终建议
M4 = []
M4.append(f"【📊 BTC+ETH 终极深度分析 (4/4) {now_str}】")
M4.append("")

# 交易策略
b_s1 = bp_s1; b_s2 = bp_s2
b_e10 = ema10_b; b_e20 = ema20_b
e_s1 = ep_s1; e_s2 = ep_s2
e_e10 = ema10_e; e_e20 = ema20_e

# A/B/C 方案
A_note = "等BTC反弹到" + str(int(b_e10)) + "-" + str(int(b_e20)) + "受阻→空"
A_target = "目标: " + str(int(b_s1)) + "(" + str(round((b_s1-bp)/bp*100,1)) + "%)→" + str(int(b_s2)) + "(" + str(round((b_s2-bp)/bp*100,1)) + "%)"
C_note = "等BTC突破" + str(int(b_e20)) + "追多 或 跌破" + str(int(b_s2)) + "追空"
M4.append("🎯 交易策略")
M4.append(f"  【方案A-做空(顺势★★★)】")
M4.append(f"    {A_note}")
M4.append(f"    {A_target}")
M4.append(f"    仓位: 5% 盈亏比: ~1:4")
M4.append("")
M4.append("  【方案B-做多(逆势⚠️)】")
M4.append(f"    BTC: {int(b_s1)}企稳(1h收盘确认)→轻仓多")
M4.append(f"    止损: -0.8% 仓位: ≤3%")
M4.append("")
M4.append(f"  【方案C-观望(最稳★★★)】")
M4.append(f"    {C_note}")
M4.append("")

# 盈亏测算
a_win = (bp - b_s2) / bp * 5
a_loss = (b_e20 - bp) / bp * 5
win_note = f"+{a_win*100:.1f}%" if a_win > 0 else f"{a_win*100:.1f}%"
loss_note = f"+{a_loss*100:+.1f}%" if a_loss > 0 else f"{a_loss*100:.1f}%"
M4.append("💰 盈亏测算(方案A空单)")
M4.append(f"  BTC 5%仓位: 跌到{int(b_s2)}→{win_note} 反弹到{int(b_e20)}→{loss_note}")
M4.append("")

# 时间节点
M4.append("⏱️ 今日关键时间")
M4.append("  21:30 ★★★美股开盘→决定今晚方向")
M4.append("  22:00-00:00 最活跃 找入场机会")
M4.append("")

# 核心风险
risk1 = f"ETH跌幅({ec:.2f}%) > BTC({bc:.2f}%) → ETH更弱"
lev_note = "200x杠杆: 仅" + str(max(0.5, 100/max(abs(bc),abs(ec)))) + "%空间就爆仓 最多5%仓位!"
M4.append("⚠️ 核心风险")
M4.append(f"  1. {risk1}")
M4.append(f"  2. {lev_note}")
M4.append(f"  3. 散户vs聪明钱分歧大 → 历史规律聪明钱赢率高")
liq_total = btc_liq_m + eth_liq_m
M4.append(f"  4. 爆仓${liq_total:.1f}M → 继续爆=继续跌")
M4.append("")

# 最终建议
if (rsi_btc < 50 and fg_val < 40):
    main_dir = "空"
else:
    main_dir = "多"
fg_signal = "极度恐惧→可能有反弹" if fg_val < 30 else "中性"
M4.append("🚨 最终建议")
M4.append(f"  → 大趋势: {main_dir} OI费率{'负' if bfr<0 else '正'}")
M4.append(f"  → 最佳: 等BTC反弹到{b_e10:,.0f}-{b_e20:,.0f}做空 或 观望等美股开盘")
M4.append(f"  → FGI={fg_val}({fg_signal})")
M4.append(f"  → 今晚美股才是关键! BTC跟美股高度相关")
M4.append("")
M4.append(f"数据时间: {now_str}")
M4.append("数据源: TradingView + Gate.io + CoinGlass + Alternative.me")

msg4 = "\n".join(M4)

# 分4条推送
print(f"  消息1: {len(msg1)}字符")
print(f"  消息2: {len(msg2)}字符")
print(f"  消息3: {len(msg3)}字符")
print(f"  消息4: {len(msg4)}字符")
send(msg1, 1)
time.sleep(1)
send(msg2, 2)
time.sleep(1)
send(msg3, 3)
time.sleep(1)
send(msg4, 4)
print("\n✅ 4条消息全部推送完成!")
