## 香橙派zero3 wifi认证
硬件:香橙派Zero3 1GB <br>
测试系统:Armbian <br>
依赖包:hostpd|dnsmasq|isc-dhcp-client|flask

用于设备启动时没有网络下，将无线网卡设置为AP模式，进行配网流程。提高设备可玩性，便携性<br>
默认SSID:Zero3AP  密码:123456789  认证页面:192.168.111.1

## 使用说明
一.环境准备
```
sudo apt update
apt install net-tools
apt install hostapd dnsmasq
apt-get install isc-dhcp-client
git clone -b master https://github.com/RamenRa/CaptivePortal-Zero3.git && cd CaptivePortal-Zero3
chmod +x sta_ap_switch.sh
```
二.安装Flask服务器

`pip install Flask`

如果提示`error: externally-managed-environment`可以有以下两个方式解决.

2-1 创建新的python环境
```
sudo apt install python3-venv
python3 -m venv ./env 
source ./env/bin/activate
pip install Flask
```

2-2 取消该保护机制
* 运行第一行find命令后,确定自己的python版本,替换掉第二行的两个`3.1x`
```
find /usr/lib/ -type d -name "*python*"     
sudo mv /usr/lib/python3.1x/EXTERNALLY-MANAGED /usr/lib/python3.1x/EXTERNALLY-MANAGED.bk
pip install Flask
```

三. 配置开机启动

`nano /etc/rc.local` # 在exit0之前添加以下 <br>
2-1方法: <br>
`/root/CaptivePortal-Zero3/env/bin/python3 /root/CaptivePortal-Zero3/main &` <br>
2-2方法: <br>
`python3 /root/CaptivePortal-Zero3/main &`
* 自行注意目录是否正确.`pwd`查看当前目录
* 脚本所在位置会生成两个日志,一个是脚本本身的和FLASK服务器的日志.
* 只有开机时会检测网络,有网则退出,否则开启配网流程.其余时间断网不会进行配网.

****
<p align="center">至此结束</p>

## 已知问题
设备启动时间较长,大约在2-3分钟左右.主要是启动dnsmasq服务和lxc网络时间较长.

配网成功后,好像认证页面没有被关闭.

****
<p align="center">以下是个人使用的记录</p>
## 安装OpenWRT及设备网口使用DHCP
安装流程主要参考[B站视频](https://www.bilibili.com/video/BV17m411f7Py/#reply250882781105)
* 由于移动设备的特性,网口配置时用了DHCP.配置文件如下,有需要的可以参考

```/etc/network/interfaces
auto lo
iface lo inet loopback

# bridge interface using DHCP
auto br0
iface br0 inet dhcp
    bridge_ports end0
    bridge_stp off
    bridge_fd 0
    bridge_maxwait 0
    bridge_waitport 0
    dns-nameservers 223.5.5.5 8.8.8.8
    metric 10

# auto wlan0
# iface wlan0 inet dhcp
#    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf
#    metric 100
```
* 取消后面四行的注释开机会自动尝试连接过的wifi.

## 运行LXC镜像报错403或者404
访问官网或者镜像站,手动下载对应版本的`incus.tar.xz`和`rootfs.tar.xz`,参考以下命令导入镜像<br>

`lxc image import ./incus.tar.xz ./rootfs.tar.xz --alias openwrt-23.05`

`lxc launch openwrt-23.05 openwrt`  # 使用openwrt-23.05镜像创建名为的openwrt容器




