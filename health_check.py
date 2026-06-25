#!/usr/bin/env python3.11
"""
守护进程：确保btc-monitor一直在跑
每60秒检查一次，发现异常自动重启
"""
import os
import subprocess
import time
import sys

LOG = "/workspace/health_check.log"
SUP_CONF = "/workspace/supervisord.conf"
SUP_PID = "/workspace/supervisord.pid"

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except:
        pass

def check_supervisord():
    """检查supervisord是否存活"""
    pid = None
    if os.path.exists(SUP_PID):
        try:
            with open(SUP_PID) as f:
                pid = int(f.read().strip())
        except:
            pass
    if pid and os.path.exists(f"/proc/{pid}"):
        return True
    # 也检查进程列表
    try:
        result = subprocess.run(
            ["pgrep", "-f", "supervisord.*workspace"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False

def start_supervisord():
    """启动supervisord"""
    log("启动supervisord...")
    try:
        subprocess.Popen(
            ["/root/.pyenv/versions/3.11.1/bin/python3.11", "-m", "supervisor.supervisord", "-c", SUP_CONF],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        time.sleep(3)
        log("supervisord已启动")
        return True
    except Exception as e:
        log(f"启动supervisord失败: {e}")
        return False

def check_btc_monitor():
    """检查btc-monitor状态"""
    try:
        result = subprocess.run(
            ["/root/.pyenv/versions/3.11.1/bin/python3.11", "-m", "supervisor.supervisorctl", "-c", SUP_CONF, "status", "btc-monitor"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        if "RUNNING" in output:
            return "running"
        elif "STOPPED" in output or "EXITED" in output or "FATAL" in output:
            return "stopped"
        else:
            return "unknown"
    except Exception as e:
        log(f"检查btc-monitor状态失败: {e}")
        return "error"

def restart_btc_monitor():
    """重启btc-monitor"""
    log("重启btc-monitor...")
    try:
        subprocess.run(
            ["/root/.pyenv/versions/3.11.1/bin/python3.11", "-m", "supervisor.supervisorctl", "-c", SUP_CONF, "restart", "btc-monitor"],
            timeout=10, check=False
        )
        log("btc-monitor已重启")
    except Exception as e:
        log(f"重启btc-monitor失败: {e}")

def check_heartbeat():
    """检查心跳文件是否超时"""
    heartbeat = "/workspace/monitor_v5.heartbeat"
    if not os.path.exists(heartbeat):
        return True  # 没有心跳文件，不判断
    try:
        mtime = os.path.getmtime(heartbeat)
        now = time.time()
        diff = now - mtime
        if diff > 600:  # 10分钟
            log(f"心跳超时{diff:.0f}秒，重启btc-monitor...")
            return False
        return True
    except Exception as e:
        log(f"检查心跳失败: {e}")
        return True

def main_loop():
    log("=== 守护进程启动 ===")
    while True:
        try:
            # 1. 检查supervisord
            if not check_supervisord():
                log("WARN: supervisord未运行")
                start_supervisord()
                time.sleep(10)
                continue

            # 2. 检查btc-monitor
            status = check_btc_monitor()
            if status == "stopped":
                log("WARN: btc-monitor异常，重启中...")
                restart_btc_monitor()
            elif status == "running":
                # 3. 检查心跳
                check_heartbeat()

        except Exception as e:
            log(f"守护循环异常: {e}")

        time.sleep(60)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        log("守护进程停止")
        sys.exit(0)
