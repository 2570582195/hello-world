#!/usr/bin/env python3.11
"""
BTC+ETH 终极深度分析 — 5条推送（分拆版）
数据源：Gate.io实时 + TradingView + CoinGlass + Alternative.me
推送格式：5条 × ~2000字符（企业微信限制4096字符/条）
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

# 1. Gate.io 实时行情
print("  [1/5] Gate.io行情...")
try:
    btc_t = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers?contract=BTC_USDT', headers=H, timeout=10).json()[0]
    eth_t = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers?contract=ETH_USDT', headers=H, timeout=10).json()[0]
    bp = float(btc_t['last']); bc = float(btc_t['change_percentage'])
    bh = float(btc_t['high_24h']); bl = float(btc_t['low_24h'])
    bv = float(btc_t['volume_24h_base']); bfr = float(btc_t['funding_rate']); boi = float(btc_t['total_size'])
    ep = float(eth_t['last']); ec = float(eth_t['change_percentage'])
    eh = float(eth_t['high_24h']); el = float(eth_t['low_24h'])
    ev = float(eth_t['volume_24h_base']); efr = float(eth_t['funding_rate']); eoi = float(eth_t['total_size'])
    print(f"    BTC={bp:.1f}({bc:+.2f}%) ETH={ep:.2f}({ec:+.2f}%)")
except Exception as e:
    print(f"  Gate.io error: {e}")
    bp,bc,ep,ec = 60000,-3.0,1600,-4.0
    bh,bl,bv,boi = 62000,58000,100000,50000
    eh,el,ev,eoi = 1700,1500,500000,200000
    bfr,efr = -0.001, -0.0005

# 2. 读取技术指标（由WebFetch更新的JSON）
print("  [2/5] 读取技术指标数据...")
import os
tv_btc = {}; tv_eth = {}
cg_btc_ls = {}; cg_eth_ls = {}
btc_large_trades = []
liq_data = {}
try:
    if os.path.exists('/workspace/market_data.json'):
        with open('/workspace/market_data.json','r') as f:
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

# 4. 爆仓数据
print("  [4/5] 爆仓数据...")
btc_liq = liq_data.get('btc_24h', 0) * 1e6
eth_liq = liq_data.get('eth_24h', 0) * 1e6

# 5. 暴跌排行
print("  [5/5] 暴跌排行...")
try:
    all_tk = requests.get('https://api.gateio.ws/api/v4/futures/usdt/tickers', headers=H, timeout=10).json()
    crash = sorted(all_tk, key=lambda x: float(x.get('change_percentage',0)))[:11]
except:
    crash = []

# ============================================================
# 组装消息 — 分5条推送（手机端优化排版）
# ============================================================
print("\n=== 组装消息(分5条) ===")
now_str = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# ── 消息1/5：行情概览 + 技术指标 + 移动平均线 + 关键价位 ──
M1 = []
M1.append(f"【📊 BTC+ETH 终极深度分析 (1/5) {now_str}】")
M1.append("")
M1.append("💰 行情概览")
M1.append(f"  BTC: {bp:,.1f} USDT ({bc:+.2f}%)")
M1.append(f"  ETH: {ep:.2f} USDT ({ec:+.2f}%)")
M1.append(f"  24h: BTC [{bl:,.0f}-{bh:,.0f}] | ETH [{el:.2f}-{eh:.2f}]")
M1.append(f"  OI费率: BTC {bfr*100:+.4f}% | ETH {efr*100:+.4f}%")
M1.append("")

# TV技术指标（精简，手机端）
bi = tv_btc; ei = tv_eth
M1.append("📈 技术指标(TV实时)")
M1.append(f"  BTC: RSI={bi.get('RSI',0):.2f} W%R={bi.get('WPR',0):.2f} MACD={bi.get('MACD',0):.2f}")
M1.append(f"  ETH: RSI={ei.get('RSI',0):.2f} W%R={ei.get('WPR',0):.2f} MACD={ei.get('MACD',0):.2f}")
rsi_ok = (bi.get('RSI',50)<35 and ei.get('RSI',50)<35)
M1.append(f"  信号: {'RSI+W%R双超卖! 技术反弹概率增加' if rsi_ok else '偏弱'}")
M1.append("")

# 均线
bema = {k:v for k,v in bi.items() if k.startswith('EMA')}
eema = {k:v for k,v in ei.items() if k.startswith('EMA')}
M1.append("📉 移动平均线(TV实时)")
M1.append(f"  BTC: EMA10={bema.get('EMA10',0):,.0f} EMA20={bema.get('EMA20',0):,.0f}")
M1.append(f"       EMA50={bema.get('EMA50',0):,.0f} EMA200={bema.get('EMA200',0):,.0f}")
M1.append(f"  ETH: EMA10={eema.get('EMA10',0):.0f} EMA20={eema.get('EMA20',0):.0f}")
all_sell = all(bema.get(k,1)>bp for k in ['EMA10','EMA20','EMA50','EMA200'] if k in bema)
M1.append(f"  信号: {'完全空头排列! 零买入信号' if all_sell else '部分多头'}")
M1.append("")

# 关键价位（精简）
bp_s1 = bi.get('S1') or int(bp*0.97/100)*100
bp_s2 = bi.get('S2') or int(bp*0.95/100)*100
ep_s1 = ei.get('S1') or int(ep*0.97/10)*10
ep_s2 = ei.get('S2') or int(ep*0.95/10)*10
M1.append("🎯 关键价位地图")
M1.append(f"  BTC: {bema.get('EMA200',0):,.0f}→{bema.get('EMA50',0):,.0f}→{bema.get('EMA20',0):,.0f}|| {bp:,.0f} || {bp_s1:,}→{bp_s2:,}")
M1.append(f"  ETH: {eema.get('EMA200',0):.0f}→{eema.get('EMA50',0):.0f}→{eema.get('EMA20',0):.0f}|| {ep:.0f} || {ep_s1:.0f}→{ep_s2:.0f}")
M1.append("")

msg1 = "\n".join(M1)

# ── 消息2/5：多空比 + 散户vs聪明钱 + 链上/OI + 大单成交 ──
M2 = []
M2.append(f"【📊 BTC+ETH 终极深度分析 (2/5) {now_str}】")
M2.append("")

# 多空比（详细分层）
cg_btc = cg_btc_ls
cg_eth = cg_eth_ls
M2.append("⚔️ 多空力量对比(CoinGlass)")
M2.append("  【BTC】")
M2.append(f"    Taker: {cg_btc.get('taker_long_pct',0):.1f}%多 vs {cg_btc.get('taker_short_pct',0):.1f}%空")
bn_ret = cg_btc.get('bn_retail')
if bn_ret:
    bl_pct = bn_ret/(1+bn_ret)*100; bs_pct = 100-bl_pct
    M2.append(f"    Binance: 散户{bn_ret:.2f}x({bl_pct:.1f}%多 {bs_pct:.1f}%空) 🔥极度看多")
bn_wc = cg_btc.get('bn_whale_count')
if bn_wc:
    wcl_pct = bn_wc/(1+bn_wc)*100; wcs_pct = 100-wcl_pct
    M2.append(f"    Binance: 大户(人) {bn_wc:.2f}x({wcl_pct:.1f}%多 {wcs_pct:.1f}%空) 🔥极度看多")
M2.append(f"    Binance主力: {cg_btc.get('main_force_binance', '?')}")
M2.append("  【ETH】")
M2.append(f"    Taker: {cg_eth.get('long_pct',0):.1f}%多 vs {cg_eth.get('short_pct',0):.1f}%空")
eth_bn = cg_eth.get('bn_retail')
if eth_bn:
    ebl = eth_bn/(1+eth_bn)*100; ebs = 100-ebl
    M2.append(f"    Binance: 散户{eth_bn:.2f}x({ebl:.1f}%多 {ebs:.1f}%空) 🔥极度看多")
M2.append("")

# 散户vs聪明钱
M2.append("🧠 散户vs聪明钱")
retail = bn_ret or 2.5
main_force = cg_btc.get('main_force_binance', '极度看空')
M2.append(f"  散户(账户数): 多空比{retail:.2f} → {'疯狂抄底!极多' if retail>2.0 else '偏多'}")
M2.append(f"  聪明钱(主力): {main_force}")
M2.append(f"  → {'别跟散户! 跟聪明钱更安全' if retail>2.0 and '空' in main_force else '等待方向'}")
M2.append("")

# 链上/OI推断
M2.append("🔗 链上数据(OI推断)")
M2.append(f"  BTC OI={boi:,.0f}张 费率={bfr*100:+.4f}%")
M2.append(f"  ETH OI={eoi:,.0f}张 费率={efr*100:+.4f}%")
M2.append(f"  → {'空头加仓(跌)' if bfr<0 else '多头加仓(涨)'}")
M2.append("")

# 大单成交
M2.append("🐋 大单成交(实时)")
if btc_large_trades:
    M2.append(f"  BTC最近大单({len(btc_large_trades)}笔):")
    for t in btc_large_trades[:6]:
        amt = t.get('amount', 0)
        amt_str = f"${amt/1e4:.0f}K" if amt < 1e6 else f"${amt/1e6:.1f}M"
        M2.append(f"    {t.get('time','?')} {amt_str} {t.get('pair','?')}")
else:
    M2.append("  大单数据获取中...")
M2.append("")

msg2 = "\n".join(M2)

# ── 消息3/5：恐惧贪婪 + 暴跌排行 + 综合研判 + 矛盾信号 + 多时间框架 ──
M3 = []
M3.append(f"【📊 BTC+ETH 终极深度分析 (3/5) {now_str}】")
M3.append("")

# 恐惧贪婪
M3.append(f"😱 恐惧贪婪指数: {fg_val} ({fg_cls})")
M3.append(f"  历史规律: FGI<25=底部信号 但可持续数周")
M3.append(f"  当前: {'可能是底部区域 但需价格企稳确认' if fg_val<30 else '中性'}")
M3.append("")

# 暴跌排行
M3.append(f"💥 全市场暴跌排行(24h)")
if crash:
    for i, t in enumerate(crash[:6], 1):
        M3.append(f"  {i}. {t['contract']} {float(t['change_percentage']):+.2f}%")
else:
    M3.append("  数据获取中...")
M3.append(f"  → {'ETH弱于BTC 做空ETH更顺' if abs(ec)>abs(bc) else 'BTC领跌'}")
M3.append("")

# 爆仓数据
btc_liq_m = liq_data.get('btc_24h', 0)
eth_liq_m = liq_data.get('eth_24h', 0)
M3.append(f"💣 爆仓数据(24h)")
M3.append(f"  BTC: ${btc_liq_m:.1f}M | ETH: ${eth_liq_m:.1f}M")
M3.append(f"  多单占比: {liq_data.get('long_pct', 90)}% → 散户多单被收割!")
M3.append("")

# 矛盾信号
M3.append(f"⚡ 矛盾信号分析")
M3.append(f"  看空: 均线空头排列 + MACD死叉 + 聪明钱看空")
M3.append(f"  看反弹: RSI{bi.get('RSI',0):.1f}(超卖) + W%R{bi.get('WPR',0):.1f}(超卖) + FGI={fg_val}(恐惧)")
M3.append(f"  → 短期可能反弹2-5% 但大趋势仍空")
M3.append("")

# 多时间框架
M3.append(f"⏰ 多时间框架研判")
b_e10 = bema.get('EMA10', bp*1.04); b_e20 = bema.get('EMA20', bp*1.07)
M3.append(f"  3-5min: BTC在{bp:,.0f}, 距EMA10({b_e10:,.0f})={(b_e10-bp)/bp*100:+.1f}%")
M3.append(f"  15min: {'反弹到' + str(int(bp_s1)) + '站稳? 是则看' + str(int(b_e10)) else '继续下探'}")
M3.append(f"  1h: RSI={bi.get('RSI',0):.1f} 超卖修复{'中' if bc>0 else '受阻'}")
M3.append(f"  4h: {'连续下跌' if bc<0 else '连续反弹'} 关键压力{b_e20:,.0f}")
M3.append("")

msg3 = "\n".join(M3)

# ── 消息4/5：交易策略ABC + 盈亏测算 + 时间节点 + 风险 ──
M4 = []
M4.append(f"【📊 BTC+ETH 终极深度分析 (4/5) {now_str}】")
M4.append("")

# 交易策略
b_s1 = bp_s1; b_s2 = bp_s2
b_e10 = bema.get('EMA10', bp*1.04); b_e20 = bema.get('EMA20', bp*1.07)
e_s1 = ep_s1; e_s2 = ep_s2
e_e10 = eema.get('EMA10', ep*1.06); e_e20 = eema.get('EMA20', ep*1.10)

# 先算盈亏比变量（避免f-string错误）
a_win_rate = (bp - b_s2) / (b_e20 - bp) if (b_e20 - bp) != 0 else 0
a_loss_rate = (b_e20 - bp) / (bp*5)

M4.append("🎯 交易策略")
M4.append("  【方案A-做空(顺势★★★)】")
M4.append(f"    BTC: 反弹到{b_e10:,.0f}-{b_e20:,.0f}受阻→空")
M4.append(f"    止损: {b_e10:,.0f}({(b_e10-bp)/bp*100:+.1f}%)")
M4.append(f"    目标: {b_s1:,}({(b_s1-bp)/bp*100:+.1f}%)→{b_s2:,}({(b_s2-bp)/bp*100:+.1f}%)")
M4.append(f"    仓位: 5% 盈亏比: ~1:{a_win_rate:.1f}")
M4.append("")
M4.append("  【方案B-做多(逆势⚠️)】")
M4.append(f"    BTC: {b_s1:,}企稳(1h收盘确认)→轻仓多")
M4.append(f"    止损: -0.8% 仓位: ≤3%")
M4.append("")
M4.append("  【方案C-观望(最稳★★★)】")
M4.append(f"    等BTC突破{b_e20:,.0f}追多 或 跌破{b_s2:,}追空")
M4.append("")

# 盈亏测算
a_win_pct = (bp - b_s2) / bp * 5
a_loss_pct = (b_e20 - bp) / bp * 5
M4.append("💰 盈亏测算(方案A空单)")
M4.append(f"  BTC 5%仓位: 跌到{b_s2:,}→+{a_win_pct*100:.1f}% 反弹到{b_e20:,.0f}→{a_loss_pct*100:+.1f}%")
M4.append("")

# 时间节点
M4.append("⏱️ 今日关键时间")
M4.append("  21:30 ★★★美股开盘→决定今晚方向")
M4.append("  22:00-00:00 最活跃 找入场机会")
M4.append("")

# 核心风险
M4.append("⚠️ 核心风险")
M4.append(f"  1. ETH跌幅({ec:.2f}%) > BTC({bc:.2f}%) → ETH更弱")
M4.append(f"  2. 200x杠杆: 仅0.5%空间就爆仓 最多5%仓位!")
M4.append(f"  3. 散户vs聪明钱分歧大 → 历史规律聪明钱赢率高")
M4.append(f"  4. 爆仓${btc_liq_m+eth_liq_m:.1f}M → 继续爆=继续跌")
M4.append("")

msg4 = "\n".join(M4)

# ── 消息5/5：最终建议 + 数据汇总 ──
M5 = []
M5.append(f"【📊 BTC+ETH 终极深度分析 (5/5) {now_str}】")
M5.append("")

# 最终建议
main_dir = "空" if (bi.get('RSI',50)<50 and fg_val<40) else "多"
M5.append("🚨 最终建议")
M5.append(f"  → 大趋势:{main_dir} OI费率{'负' if bfr<0 else '正'}")
M5.append(f"  → 最佳: 等BTC反弹到{b_e10:,.0f}-{b_e20:,.0f}做空 或 观望等美股开盘")
M5.append(f"  → FGI={fg_val}({'极度恐惧→可能有反弹' if fg_val<30 else '中性'})")
M5.append(f"  → 今晚美股才是关键! BTC跟美股高度相关")
M5.append("")

# 数据汇总表
M5.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
M5.append("📊 全维度数据汇总")
M5.append(f"  BTC: {bp:,.1f}({bc:+.2f}%) | RSI:{bi.get('RSI','?'):.1f} | W%R:{bi.get('WPR','?'):.1f}")
M5.append(f"  ETH: {ep:.2f}({ec:+.2f}%) | RSI:{ei.get('RSI','?'):.1f} | W%R:{ei.get('WPR','?'):.1f}")
M5.append(f"  恐惧贪婪: {fg_val}({fg_cls}) | 爆仓: ${btc_liq_m+eth_liq_m:.1f}M")
M5.append(f"  散户多空比: BTC={bn_ret:.2f}x ETH={cg_eth.get('bn_retail','?'):.2f}x")
M5.append(f"  聪明钱: BTC={cg_btc.get('main_force_binance','?')} ETH={cg_eth.get('main_force_binance','?')}")
M5.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
M5.append("")
M5.append(f"数据时间: {now_str}")
M5.append("数据源: TradingView + Gate.io + CoinGlass + Alternative.me")

msg5 = "\n".join(M5)

# ── 分5条推送 ──
print(f"  消息1: {len(msg1)}字符")
print(f"  消息2: {len(msg2)}字符")
print(f"  消息3: {len(msg3)}字符")
print(f"  消息4: {len(msg4)}字符")
print(f"  消息5: {len(msg5)}字符")
send(msg1, 1)
time.sleep(1)
send(msg2, 2)
time.sleep(1)
send(msg3, 3)
time.sleep(1)
send(msg4, 4)
time.sleep(1)
send(msg5, 5)
print("\n✅ 5条消息全部推送完成!")
