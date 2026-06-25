#!/usr/bin/env python3.11
"""
TradingView 关键位自动化抓取脚本
使用 Playwright 模拟浏览器访问TV图表，提取关键支撑/压力位
"""
from playwright.sync_api import sync_playwright
import json, time, re

def fetch_tv_levels(symbol="BTCUSDT", exchange="BINANCE", interval="1h"):
    """
    抓取TV技术分析页面的关键位
    返回: dict 包含 pivot/s1/s2/r1/r2/support/resistance
    """
    results = {}
    with sync_playwright() as p:
        # 启动浏览器（无头模式）
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        page = context.new_page()
        try:
            # 访问TV技术分析页面
            url = f"https://www.tradingview.com/symbols/{exchange}:{symbol}/technicals/"
            print(f"[TV] 正在访问: {url}")
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            time.sleep(5)  # 等待JS渲染

            # 尝试提取Pivot Points数据
            # 方法1: 定位Pivots表格
            pivots = {}
            try:
                # 找包含"Pivot"的文本
                pivot_section = page.locator('text=/[Pp]ivot/i').first
                if pivot_section:
                    # 向上找父容器
                    container = pivot_section.locator('..').first
                    text = container.inner_text(timeout=5000)
                    print(f"[TV] 找到Pivot区域:\n{text[:500]}")
                    
                    # 用正则提取数字
                    nums = re.findall(r'[\d,]+\.?\d*', text)
                    if nums:
                        nums = [float(n.replace(',', '')) for n in nums]
                        if len(nums) >= 3:
                            pivots['P'] = nums[0]
                            pivots['S1'] = nums[1] if len(nums) > 1 else None
                            pivots['R1'] = nums[2] if len(nums) > 2 else None
                            if len(nums) > 3:
                                pivots['S2'] = nums[3]
                            if len(nums) > 4:
                                pivots['R2'] = nums[4]
            except Exception as e:
                print(f"[TV] Pivot提取失败: {e}")

            # 方法2: 直接抓页面所有文本，用正则找关键位
            try:
                body_text = page.inner_text('body')
                # 找Support/Resistance
                # 示例: "Support: 60,229  Resitance: 62,568"
                support_match = re.search(r'[Ss]upport[:\s]*([\d,]+\.?\d*)', body_text)
                resist_match = re.search(r'[Rr]esist[:\s]*([\d,]+\.?\d*)', body_text)
                
                if support_match:
                    results['support'] = float(support_match.group(1).replace(',', ''))
                if resist_match:
                    results['resistance'] = float(resist_match.group(1).replace(',', ''))
                    
                # 找Pivot
                pivot_match = re.search(r'[Pp]ivot[:\s]*([\d,]+\.?\d*)', body_text)
                if pivot_match:
                    results['pivot'] = float(pivot_match.group(1).replace(',', ''))
                    
                print(f"[TV] 正则提取: Support={results.get('support')}, Resist={results.get('resistance')}, Pivot={results.get('pivot')}")
            except Exception as e:
                print(f"[TV] 正则提取失败: {e}")

            results['pivots'] = pivots
            results['symbol'] = symbol
            results['exchange'] = exchange
            results['interval'] = interval

        except Exception as e:
            print(f"[TV] 页面访问失败: {e}")
            results['error'] = str(e)
        finally:
            browser.close()
    return results


if __name__ == "__main__":
    print("=== TradingView 关键位抓取 ===")
    for sym, exc in [("BTCUSDT", "BINANCE"), ("ETHUSDT", "BINANCE")]:
        print(f"\n{'='*50}")
        print(f"  抓取 {sym} ({exc})")
        r = fetch_tv_levels(sym, exc, "1h")
        print(f"  结果: {json.dumps(r, indent=2, ensure_ascii=False)}")
        time.sleep(3)
    print("\n=== 完成 ===")
