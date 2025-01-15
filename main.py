import os
import subprocess
import time
from flask import Flask, request, render_template_string
import logging

auto_connect_wifi = False  # 先尝试自动连接wifi
flask_server_started = False  # 标志变量，确保 Flask 服务器只启动一次
app = Flask(__name__)
current_dir = os.path.dirname(os.path.abspath(__file__))
script_path = os.path.join(current_dir, "sta_ap_switch.sh")
wpa_supplicant_conf = "/etc/wpa_supplicant/wpa_supplicant.conf"
log_file = os.path.join(current_dir, 'run.log')
if os.path.exists(log_file):
    open(log_file, 'w').close()
logging.basicConfig(
    filename=log_file,  # 指定日志文件
    level=logging.DEBUG,  # 设置日志级别
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志格式
    filemode='a'  # 追加模式写入文件
)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Setup</title>
</head>
<body>
    <h1>WiFi Setup</h1>
    <form action="/submit" method="post">
        <label for="ssid">SSID:</label><br>
        <input type="text" id="ssid" name="ssid" required><br>
        <label for="password">Password:</label><br>
        <input type="password" id="password" name="password" required><br><br>
        <button type="submit">Submit</button>
    </form>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE)


@app.route("/submit", methods=["POST"])
def submit():
    # logging.info("submit Script path:", script_path)
    ssid = request.form["ssid"]
    password = request.form["password"]
    configure_wifi(ssid, password)
    return "Configuring WiFi... Please reconnect if it fails."


def configure_wifi(ssid, password):
    # logging.info("configure_wifi Script path:", script_path)
    same = False

    # 切换网卡到 STA 模式
    switch_to_sta_mode()
    time.sleep(10)
    if not os.path.exists(wpa_supplicant_conf):
        logging.info(f"创建wpa_supplicant.conf")
        with open(wpa_supplicant_conf, "w") as f:
            # 写入默认的配置内容
            f.write("ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n")
            f.write("update_config=1\n")
            f.write("country=CN\n")  # 根据实际情况选择国家
            f.write("\n")

    # 1. 删除可能存在的控制文件，避免文件冲突
    ctrl_iface_file = "/var/run/wpa_supplicant/wlan0"
    if os.path.exists(ctrl_iface_file):
        logging.info(f"删除之前的文件: {ctrl_iface_file}")
        os.remove(ctrl_iface_file)

    # 2. 读取现有配置文件内容
    with open(wpa_supplicant_conf, "r") as f:
        existing_config = f.read()

    # 3. 检查是否已有相同的 SSID 和密码
    if f"ssid=\"{ssid}\"" in existing_config and f"psk=\"{password}\"" in existing_config:
        # logging.info(f"SSID: {ssid} with the same password already exists in the configuration file.")
        same = True

    # 4. 如果没有相同的配置，则将新配置添加到文件末尾
    if not same:
        with open(wpa_supplicant_conf, "a") as f:
            f.write(f"\nnetwork={{\n")
            f.write(f"    ssid=\"{ssid}\"\n")
            f.write(f"    psk=\"{password}\"\n")
            f.write(f"}}\n")
        logging.info(f"检查到新的wifi配置，SSID: {ssid}.")

    # 6. 启动 wpa_supplicant
    try:
        subprocess.run(["sudo", "pkill", "wpa_supplicant"], check=True)
        subprocess.run(["sudo", "wpa_supplicant", "-B", "-i", "wlan0", "-c", wpa_supplicant_conf], check=True)
        subprocess.run(["sudo", "dhclient", "-r", "wlan0"], check=True)
        subprocess.run(["sudo", "dhclient", "wlan0"], check=True)
        logging.info("wpa_supplicant 已尝试连接wifi.")

    except subprocess.CalledProcessError as e:
        logging.info(f"启动 wpa_supplicant错误: {e}")

    # 检查是否连接成功
    if check_wifi_connection():
        logging.info("成功通过CaptivePortal连接 Wi-Fi.")
        exit(0)
    else:
        logging.info("通过CaptivePortal连接 Wi-Fi失败")
        switch_to_ap_mode()

def check_wifi_connection(target_ssid=None):
    """
    检查是否已连接到指定的 Wi-Fi
    :param target_ssid: 要检查的目标 SSID
    :return: 是否连接到目标 Wi-Fi (True/False)
    """
    try:
        # 执行 iw 命令获取连接状态
        result = subprocess.run(
            ["iw", "dev", "wlan0", "link"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        # 检查输出是否包含 "Connected to"
        if "Connected to" in result.stdout:
            # 查找 SSID 信息
            if target_ssid:
                for line in result.stdout.splitlines():
                    if line.strip().startswith("SSID:"):
                        connected_ssid = line.split("SSID:")[1].strip()
                        # 判断 SSID 是否匹配
                        return connected_ssid == target_ssid
            else:
                return True
    except FileNotFoundError:
        logging.info("iw 命令不可用，请检查系统环境。")
    except Exception as e:
        logging.info(f"检查 Wi-Fi 连接时发生错误: {e}")
    return False


def switch_to_sta_mode():
    """切换到 STA 模式"""
    # logging.info("Switching to STA mode...")
    try:
        subprocess.run([script_path, "sta"], check=True)
    except subprocess.CalledProcessError as e:
        # logging.info(f":{script_path}")
        logging.info(f"STA mode启动失败: {e}")


def switch_to_ap_mode():
    """切换到 AP 模式"""
    # logging.info("Switching to AP mode...")
    try:
        subprocess.run([script_path, "ap"], check=True)
    except subprocess.CalledProcessError as e:
        logging.info(f"AP mode启动失败: {e}")


def check_wlan0_status():
    result = subprocess.run(["ip", "addr", "show", "wlan0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout.decode()
    if "state UP" in output:
        return True
    return False


def activate_wlan0():
    # logging.info("Activating wlan0...")
    subprocess.run(["ip", "link", "set", "wlan0", "up"])
    # subprocess.run(["ip", "addr", "add", "192.168.4.1/24", "dev", "wlan0"])


def check_connection():
    # 要尝试的 IP 地址列表
    ip_addresses = ["180.76.76.76", "223.5.5.5", "8.8.8.8"]
    success_count = 0
    failure_count = 0

    # 遍历每个 IP 地址，尝试 ping 通
    for ip in ip_addresses:
        try:
            result = subprocess.run(["ping", "-c", "1", ip], stdout=subprocess.PIPE)
            if result.returncode == 0:
                success_count += 1  # ping 成功
            else:
                failure_count += 1  # ping 失败
        except Exception as e:
            failure_count += 1  # 异常情况下认为 ping 失败
        if success_count >= 1:
            # logging.info("网络有效")
            return True
        elif failure_count >= 2:
            # logging.info("网络无效")
            return False
    return False


def start_flask_server():
    """启动 Flask 服务器"""
    global flask_server_started
    # 动态构造虚拟环境的 bin 路径
    env_dir = os.path.join(current_dir, "env/bin")

    # 设置 FLASK_APP 环境变量
    os.environ["FLASK_APP"] = __file__

    # 复制当前环境变量并修改 PATH
    env = os.environ.copy()
    env["PATH"] = f"{env_dir}:{env['PATH']}"  # 将虚拟环境路径加到 PATH 前面

    # 设置日志文件
    log_file = os.path.join(current_dir, "flask_server.log")

    # 清空日志文件
    if os.path.exists(log_file):
        os.remove(log_file)

    # 启动 Flask 服务器并重定向输出
    with open(log_file, "a") as log:
        subprocess.Popen(
            ["flask", "run", "--host=0.0.0.0", "--port=80"],
            env=env,
            stdout=log,  # 重定向标准输出
            stderr=log   # 重定向错误输出
        )
    flask_server_started = True


def main():
    global flask_server_started
    while True:
        if not flask_server_started and check_connection():
            logging.info("网络连接正常.")
            switch_to_sta_mode()
            time.sleep(5)
            break
        elif auto_connect_wifi:
            if os.path.exists(wpa_supplicant_conf):  # 如果存在wifi配置文件 尝试从文件连接
                subprocess.run(["sudo", "wpa_supplicant", "-B", "-i", "wlan0", "-c", wpa_supplicant_conf], check=True)
            else:
                logging.info("没有wifi配置文件，自动连接失败")
        if not check_wlan0_status():
            activate_wlan0()
        if not flask_server_started:
            start_flask_server()
            logging.info("网络连接错误，尝试开启AP模式.")
            switch_to_ap_mode()
        if check_wifi_connection():  # 成功连接wifi
            break
        time.sleep(5)


if __name__ == "__main__":
    main()


