#!/usr/bin/env python3
"""
监控守护进程 v3 - 彻底防掉线
1. 心跳检测：v5每5分钟touch心跳文件，守护检测超时（>10分钟）则重启
2. 进程检测：v5进程不存在则重启
3. v5连续失败5次会exit(1)，守护收到也重启
4. 指数退避：连续重启失败则等待时间指数增长（最长5分钟）
"""

import os
import sys
import time
import subprocess
from datetime import datetime

SCRIPT = "/workspace/btc_eth_monitor_v5.py"
HEARTBEAT = "/workspace/monitor_v5.heartbeat"
LOG_FILE = "/workspace/monitor_watchdog3.log"

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}\n"
    print(line, end='')
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line)
    except:
        pass


def check_heartbeat():
    """检查心跳文件是否超过10分钟没更新"""
    if not os.path.exists(HEARTBEAT):
        return False
    try:
        mtime = os.path.getmtime(HEARTBEAT)
        now = time.time()
        return (now - mtime) <= 600  # 10分钟
    except:
        return False


def check_process():
    """检查v5进程是否存在"""
    try:
        out = subprocess.check_output(
            "ps aux | grep btc_eth_monitor_v5 | grep -v grep | wc -l",
            shell=True, timeout=5)
        return int(out.strip()) > 0
    except:
        return False


def start_monitor():
    """启动v5监控脚本"""
    try:
        subprocess.Popen(
            [sys.executable, "-u", SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        log("🚀 监控v5启动成功")
        # 等待5秒让v5初始化
        time.sleep(5)
        return True
    except Exception as e:
        log(f"❌ 监控v5启动失败: {e}")
        return False


def restart_monitor(reason=""):
    """重启v5"""
    log(f"🔄 重启监控v5... 原因: {reason}")
    # 先杀掉所有v5进程
    try:
        subprocess.run(
            "ps aux | grep btc_eth_monitor_v5 | grep -v grep | awk '{print $2}' | xargs -r kill -9",
            shell=True, timeout=5)
    except:
        pass
    time.sleep(2)
    return start_monitor()


def main():
    log("🛡️ 守护进程v3启动")
    log(f"监控脚本: {SCRIPT}")
    log(f"心跳文件: {HEARTBEAT}")

    # 初始启动
    if not check_process():
        start_monitor()

    fail_count = 0
    restart_delay = 5  # 初始重启延迟5秒

    while True:
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 检测1：进程是否存在
            proc_alive = check_process()

            # 检测2：心跳是否正常
            heartbeat_alive = check_heartbeat() if proc_alive else False

            if proc_alive and heartbeat_alive:
                # 正常
                fail_count = 0
                restart_delay = 5
                log(f"✅ 监控正常 (进程+心跳)")
                time.sleep(60)
                continue

            if proc_alive and not heartbeat_alive:
                log(f"⚠️ 进程存在但心跳超时 (>10分钟)")
                restart_monitor("心跳超时")
                time.sleep(restart_delay)
                continue

            if not proc_alive:
                log(f"⚠️ 监控进程不存在")
                success = restart_monitor("进程不存在")
                if not success:
                    fail_count += 1
                    restart_delay = min(300, 5 * (2 ** min(fail_count, 6)))  # 指数退避，最长5分钟
                    log(f"❌ 重启失败，{restart_delay}秒后重试 (连续失败{fail_count}次)")
                else:
                    fail_count = 0
                    restart_delay = 5
                time.sleep(restart_delay)
                continue

            # 不应该到这里
            time.sleep(60)

        except KeyboardInterrupt:
            log("⏹️ 守护进程停止")
            break
        except Exception as e:
            log(f"❌ 守护进程异常: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
