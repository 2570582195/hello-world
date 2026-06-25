#!/usr/bin/env python3.11
"""
BTC/ETH 监控守护进程 v1.0

功能：
- 每60秒检查 btc_eth_monitor_v5.py 是否存活
- 不存活则立即重启（无需任何外部工具）
- 守护进程自身也具备防崩溃能力

使用方式：
  nohup python3.11 -u /workspace/guardian.py > /dev/null 2>&1 &
  或由 .bashrc 自动启动
"""

import os
import sys
import time
import subprocess
import signal

# ===== 配置 =====
MONITOR_SCRIPT = "/workspace/btc_eth_monitor_v5.py"
PYTHON = "/root/.pyenv/versions/3.11.1/bin/python3.11"
LOG = "/workspace/guardian.log"
CHECK_INTERVAL = 60  # 检查间隔(秒)

def log(msg):
    """写日志"""
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {msg}"
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass
    print(line, flush=True)

def get_monitor_pid():
    """获取监控脚本的PID"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "btc_eth_monitor_v5.py"],
            capture_output=True, text=True, timeout=10,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/root/.pyenv/shims:/root/.pyenv/versions/3.11.1/bin"}
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = [int(p) for p in result.stdout.strip().split('\n') if p.strip()]
            return pids[0] if pids else None
    except Exception as e:
        log(f"获取PID异常: {e}")
    return None

def start_monitor():
    """启动监控脚本（后台daemon化）"""
    log("正在启动监控脚本...")
    try:
        proc = subprocess.Popen(
            [PYTHON, "-u", MONITOR_SCRIPT],
            stdout=open("/workspace/monitor_stdout.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 新session，脱离父进程
            cwd="/workspace",
            env=os.environ.copy()
        )
        log(f"已发出启动命令，等待验证... (parent_pid={proc.pid})")
        time.sleep(8)  # 等待脚本初始化+第一次API请求
        
        pid = get_monitor_pid()
        if pid:
            log(f"✅ 监控已启动 (PID={pid})")
            return True
        else:
            log("❌ 启动后未找到进程")
            return False
    except Exception as e:
        log(f"❌ 启动失败: {e}")
        return False

def is_monitor_running():
    """检查监控是否真的在运行（且是当前会话拉的）"""
    pid = get_monitor_pid()
    if not pid:
        return False
    # 额外检查 PPID 是否是当前 guardian 的 PID
    try:
        import psutil
        p = psutil.Process(pid)
        ppid = p.ppid()
        my_pid = os.getpid()
        # 如果 monitor 的父进程不是我，说明是之前会话继承的，要杀掉重拉
        if ppid != my_pid:
            log(f"⚠️ 监控(PID={pid})的父进程是{pcid}不是我({my_pid})，杀掉重拉")
            os.kill(pid, 9)
            time.sleep(2)
            return False
    except:
        pass  # psutil 可能没装，跳过PPID检查
    # 最后检查 /proc 是否存在
    return os.path.exists(f"/proc/{pid}")

def trim_log():
    """日志只保留最近200行"""
    try:
        with open(LOG, "r") as f:
            lines = f.readlines()
        if len(lines) > 200:
            with open(LOG, "w") as f:
                f.writelines(lines[-200:])
    except:
        pass

def main():
    log("=" * 50)
    log("🛡️  守护进程启动")
    log(f"   监控脚本: {MONITOR_SCRIPT}")
    log(f"   检查间隔: {CHECK_INTERVAL}秒")
    
    consecutive_failures = 0
    max_failures = 5
    
    while True:
        try:
            running = is_monitor_running()
            
            if not running:
                consecutive_failures += 1
                log(f"⚠️  监控进程不存在 (连续第{consecutive_failures}次)")
                
                if consecutive_failures <= max_failures:
                    ok = start_monitor()
                    if not ok:
                        log("❌ 启动失败，30秒后重试...")
                        time.sleep(30)
                    else:
                        consecutive_failures = 0  # 重置计数
                        trim_log()
                else:
                    log(f"❌ 连续{max_failures}次启动失败，停止尝试（防止无限循环）")
                    log("   请手动运行: cd /workspace && ./start_monitor.sh")
                    consecutive_failures = 0  # 下个循环再试
                    time.sleep(120)
            else:
                pid = get_monitor_pid()
                if int(time.time()) % 600 < CHECK_INTERVAL:  # 约10分钟打一次心跳
                    log(f"💓 心跳正常 (PID={pid})")
                consecutive_failures = 0
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("⏹️  收到中断信号，退出")
            break
        except Exception as e:
            log(f"💥 未捕获异常: {e}")
            time.sleep(30)

if __name__ == "__main__":
    # 忽略SIGTERM和SIGHUP，让自己不容易被误杀
    signal.signal(signal.SIGTERM, lambda s,f: None)
    signal.signal(signal.SIGHUP, lambda s,f: None)
    
    try:
        main()
    except Exception as e:
        log(f"守护进程致命错误: {e}")
        sys.exit(1)
