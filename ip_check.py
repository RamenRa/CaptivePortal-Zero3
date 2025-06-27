#!/usr/bin/env python3
import subprocess
# import re
import time
import logging
import json
# import os
import requests
import re
from pathlib import Path
# 脚本使用`chomod +x 脚本名称` 给脚本添加可执行权限。在`/etc/rc.local`文件写入python "脚本绝对路径" & 即可记得加& 后台执行。或使用其他开机启动方式

# 通知配置 - 请替换为您自己的token
SERVERCHAN_TOKEN = ""  # 支持server3  sctpxxxxxxxxxxxxxxxxxxxx
PUSHPLUS_TOKEN = ""   # 登陆PushPlus后，复制token
Try_All_Chan = True   # 为True时，同时让Server3和PushPlus推送通知。为False时，Server3成功，则不尝试PushPlus

# 获取脚本所在目录
SCRIPT_DIR = Path(__file__).parent.resolve()
IP_RECORD_FILE = SCRIPT_DIR / "ip_record.txt"

def setup_logging():
    """设置中文日志记录"""
    logging.basicConfig(
        filename='/var/log/ip_monitor.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.info("IP监控服务已启动")


def get_br0_ip():
    """获取br0网卡的IPv4地址"""
    try:
        result = subprocess.run(
            ['ip', '-4', 'addr', 'show', 'br0'],
            capture_output=True,
            text=True,
            check=True
        )
        match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)/', result.stdout)
        if match:
            return match.group(1)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logging.error(f"获取br0 IP地址时出错: {str(e)}")
    return None


def get_openwrt_ip():
    """获取OpenWrt容器的IPv4地址"""
    try:
        result = subprocess.run(
            ['lxc', 'list', 'openwrt', '--format', 'json'],
            capture_output=True,
            text=True,
            check=True
        )
        containers = json.loads(result.stdout)

        if not containers:
            logging.warning("lxc list输出中未找到任何容器")
            return None

        openwrt_container = next((c for c in containers if c.get('name') == 'openwrt'), None)

        if not openwrt_container:
            logging.warning("lxc list输出中未找到OpenWrt容器")
            return None

        if openwrt_container.get('status', '').lower() != 'running':
            logging.warning("OpenWrt容器未运行")
            return None

        state = openwrt_container.get('state', {})
        network = state.get('network', {})
        br_lan = network.get('br-lan', {})
        addresses = br_lan.get('addresses', [])

        for addr in addresses:
            if addr.get('family') == 'inet':
                return addr.get('address')

        logging.warning("未找到br-lan接口的IPv4地址")
        return None

    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        logging.error(f"获取OpenWrt IP地址时出错: {str(e)}")
    return None


def read_previous_ips():
    """读取之前记录的IP地址"""
    if not IP_RECORD_FILE.exists():
        return None, None

    try:
        with open(IP_RECORD_FILE, 'r') as f:
            data = f.read().strip().split(',')
            if len(data) == 2:
                br0_ip = data[0].split(':')[1].strip()
                openwrt_ip = data[1].split(':')[1].strip()
                return br0_ip, openwrt_ip
    except Exception as e:
        logging.error(f"读取IP记录时出错: {str(e)}")

    return None, None


def save_current_ips(br0_ip, openwrt_ip):
    """保存当前IP地址到文件"""
    try:
        with open(IP_RECORD_FILE, 'w') as f:
            f.write(f"br0_ip:{br0_ip},openwrt_ip:{openwrt_ip}")
        logging.info(f"已保存当前IP: br0={br0_ip}, openwrt={openwrt_ip}")
    except Exception as e:
        logging.error(f"保存IP记录时出错: {str(e)}")


def send_serverchan(title, content):
    """使用ServerChan发送通知"""
    if not SERVERCHAN_TOKEN:
        logging.warning("未配置ServerChan Token，跳过通知")
        return False

    try:
        # 处理复合token格式 (sct12345t,your_token)
        if ',' in SERVERCHAN_TOKEN:
            before_comma, after_comma = SERVERCHAN_TOKEN.split(',', 1)
            if before_comma.startswith('sctp'):
                token = after_comma  # 使用公众号token
            else:
                token = before_comma  # 使用server3 token
        else:
            token = SERVERCHAN_TOKEN

        # 处理特殊格式token (sctp12345t)
        if token.startswith('sctp'):
            match = re.match(r'sctp(\d+)t', token)
            if match:
                num = match.group(1)
                url = f'https://{num}.push.ft07.com/send/{token}.send'
            else:
                logging.error("ServerChan Token格式错误")
                return False
        else:
            url = f'https://sctapi.ftqq.com/{token}.send'

        params = {
            'title': title,
            'desp': content
        }

        response = requests.post(url, json=params)
        result = response.json()

        if result.get('code') == 0:
            logging.info("ServerChan通知发送成功")
            return True
        else:
            error_msg = result.get('message', '未知错误')
            logging.error(f"ServerChan通知发送失败: {error_msg}")
            return False

    except Exception as e:
        logging.error(f"ServerChan通知异常: {str(e)}")
        return False


def send_pushplus(title, content):
    """使用PushPlus发送通知"""
    if not PUSHPLUS_TOKEN:
        logging.warning("未配置PushPlus Token，跳过通知")
        return False

    try:
        url = f"http://www.pushplus.plus/send/{PUSHPLUS_TOKEN}"

        data = {
            "title": title,
            "content": content,
            "template": "markdown"
        }

        response = requests.post(url, json=data)
        result = response.json()

        if result.get('code') == 200:
            logging.info("PushPlus通知发送成功")
            return True
        else:
            error_msg = result.get('msg', '未知错误')
            logging.error(f"PushPlus通知发送失败: {error_msg}")
            return False

    except Exception as e:
        logging.error(f"PushPlus通知异常: {str(e)}")
        return False


def send_notification(title, content):
    server_chan_flag = False
    pushplus_flag = False
    # 首先尝试ServerChan
    if SERVERCHAN_TOKEN:
        server_chan_flag = send_serverchan(title, content)
        if server_chan_flag and not Try_All_Chan:
            return True

    # 如果ServerChan失败或未配置，尝试PushPlus
    if PUSHPLUS_TOKEN:
        pushplus_flag = send_pushplus(title, content)
        if pushplus_flag:
            return True

    # 如果都没有配置或全部失败
    if not SERVERCHAN_TOKEN and not PUSHPLUS_TOKEN:
        logging.warning("未配置任何通知Token，无法发送通知")
    elif not server_chan_flag:
        logging.error("Server酱通知发送失败")
    elif not pushplus_flag:
        logging.error("pushplus_通知发送失败")
    return False


def check_and_notify(current_br0, current_openwrt):
    """检查IP变化并发送通知"""
    prev_br0, prev_openwrt = read_previous_ips()

    # 如果这是第一次运行，只保存不通知
    if prev_br0 is None or prev_openwrt is None:
        logging.info("首次运行 - 保存初始IP地址")
        save_current_ips(current_br0 or "未获取", current_openwrt or "未获取")
        return

    # 检查IP变化
    br0_changed = current_br0 != prev_br0 and current_br0 is not None
    openwrt_changed = current_openwrt != prev_openwrt and current_openwrt is not None

    if br0_changed or openwrt_changed:
        # 构建中文通知消息（Markdown格式）
        title = "📡 检测到IP地址变更"

        # 创建Markdown格式的内容
        content = "## 🌐 IP地址变更通知\n\n"

        if br0_changed or openwrt_changed:
            content += "### 📌 旧的IP地址信息:\n"
            if br0_changed:
                content += f"- **br0网卡IP**: `{prev_br0}`\n"
            if openwrt_changed:
                content += f"- **OpenWrt容器IP**: `{prev_openwrt}`\n"
            content += "\n"

        content += "### 🔍 当前IP状态:\n"
        content += f"- **br0网卡IP**: `{current_br0 or '未获取'}`\n"
        content += f"- **OpenWrt容器IP**: `{current_openwrt or '未获取'}`\n\n"

        content += f"⏱️ **检测时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # 添加一些有用的分隔和提示
        content += "---\n"
        content += "> ℹ️ 此通知由OrangePi Zero 3的IP监控系统自动发送\n"

        # 发送通知
        if send_notification(title, content):
            logging.info("IP变更通知已发送")
        else:
            logging.warning("IP变更通知发送失败")

        # 保存新IP
        save_current_ips(current_br0 or "未获取", current_openwrt or "未获取")
    else:
        logging.info("IP地址未发生变化")


def main():
    """主监控函数"""
    setup_logging()

    # 等待网络初始化（第一次获取可能失败）
    max_retries = 5
    retry_delay = 30

    for attempt in range(max_retries):
        br0_ip = get_br0_ip()
        openwrt_ip = get_openwrt_ip()

        if br0_ip is not None and openwrt_ip is not None:
            break

        logging.warning(f"尝试 {attempt + 1}/{max_retries}: 获取IP失败. {retry_delay}秒后重试...")
        time.sleep(retry_delay)
    else:
        logging.error("多次尝试后仍无法获取IP地址")
        br0_ip = "获取失败"
        openwrt_ip = "获取失败"

    # 记录当前状态
    status = {
        "br0": br0_ip or "未获取",
        "openwrt": openwrt_ip or "未获取"
    }

    logging.info(f"初始IP - br0: {status['br0']}, OpenWrt: {status['openwrt']}")
    print(f"初始IP - br0: {status['br0']}, OpenWrt: {status['openwrt']}")

    # 检查变化并通知
    check_and_notify(status["br0"], status["openwrt"])

    # 持续监控（每分钟检查一次）
    # while True:
    #     time.sleep(60)
    #
    #     br0_ip = get_br0_ip()
    #     openwrt_ip = get_openwrt_ip()
    #
    #     status = {
    #         "br0": br0_ip or "未获取",
    #         "openwrt": openwrt_ip or "未获取"
    #     }
    #
    #     logging.info(f"当前IP - br0: {status['br0']}, OpenWrt: {status['openwrt']}")
    #     print(f"当前IP - br0: {status['br0']}, OpenWrt: {status['openwrt']}")
    #
    #     # 检查变化并通知
    #     check_and_notify(status["br0"], status["openwrt"])


if __name__ == "__main__":
    main()
