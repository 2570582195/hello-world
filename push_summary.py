import requests
import json
from datetime import datetime

webhook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=fb585df5-b652-481d-ba71-4f0dddbc2aee"

msg = """【⚠️ BTC+ETH监控脚本问题总结 | 07:45】

━━━━━━━━━━━━ 🚨 已发现的问题 ━━━━━━━━━━━

【1】数据源延迟问题 ✅ 已解决
  - 问题：Binance/OKX/CoinGecko API在当前环境全部超时/SSL错误
  - 解决：已切换到Gate.io API（你用的芝麻开门）
  - 状态：✅ Gate.io API实时可用，无缓存！

【2】TradingView数据缓存问题 ⚠️ 仍存在
  - 问题：TV页面是JS动态加载，直接抓取可能拿到缓存数据
  - 影响：技术指标更新可能有5-15分钟延迟
  - 解决方向：需要用到TV API key 或者继续用Gate API（实时价格）+ TV（技术指标）组合

【3】监控脚本重复运行问题 ⚠️ 需检查
  - 问题：之前启动了PID 79388，后来又启动152771
  - 影响：可能两个脚本同时运行，重复推送
  - 建议：先杀掉旧进程，只保留最新的

【4】技术指标无法自动获取问题 ⚠️ 核心限制#
  - 问题：技术指标（RSI/MACD/均线）只能从TV抓取，而TV有缓存
  - 影响：监控脚本只能监控价格，无法监控指标触发#
  - 解决方向：
    方案A：接入TradingView Alert Webhook（需要TV账号+付费）
    方案B：自己计算技术指标（需要K线数据，复杂）
    方案C：只用价格监控，指标人工判断

【5】企微推送格式问题 ⚠️ 待优化
  - 问题：推送消息太长，手机端显示不全
  - 建议：分段推送或者精简格式#

━━━━━━━━━━━━ 🔧 建议操作 ━━━━━━━━━━━

【立即执行】
  1. 杀掉旧进程：`kill 79388`
  2. 保留新的：`btc_eth_monitor_v2.py`（PID 152771）
  3. 测试推送：看看企微能不能收到完整消息

【后续升级方向】
  1. 接入TradingView Alert Webhook（最精准）
  2. 或者接入Gate.io的K线API自己算指标
  3. 分段推送（价格报警一段，技术指标一段）

━━━━━━━━━━━━ 📊 当前状态 ━━━━━━━━━━━

✅ Gate.io API对接完成（实时价格无缓存）
✅ 企微Webhook配置完成
⚠️ TV技术指标可能有5-15分钟缓存延迟
⚠️ 两个监控脚本同时在跑（需清理）
⚠️ 技术指标无法自动监控（只能人工判断）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
推送时间：""" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

payload = {
    "msgtype": "text",
    "text": {
        "content": msg
    }
}

resp = requests.post(webhook, json=payload, timeout=10)
print(f"状态码: {resp.status_code}")
print(f"响应: {resp.text}")