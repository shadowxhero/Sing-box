import subprocess, sys

def run_cmd(cmd):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error running: {cmd}\n{res.stderr}")
        sys.exit(res.returncode)
    return res.stdout.strip()

print("Fetching latest sing-box.sh from upstream...")
run_cmd("git show upstream/main:sing-box.sh > sing-box.sh")

with open("sing-box.sh", "r", encoding="utf-8", newline="\n") as f:
    text = f.read()

# 1. 替换快捷指令里的原作者地址为用户的仓库地址
text = text.replace(
    'https://raw.githubusercontent.com/eooce/sing-box/main/sing-box.sh',
    'https://raw.githubusercontent.com/shadowxhero/Sing-box/main/sing-box.sh'
)

# 2. 修复 Nginx 订阅 404
old_nginx = """    location = /$password {
        alias /etc/sing-box/sub.txt;
        default_type 'text/plain; charset=utf-8';
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }"""

new_nginx = """    location = /$password {
        default_type 'text/plain; charset=utf-8';
        root /etc/sing-box;
        try_files /sub.txt =404;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }"""
if old_nginx in text:
    text = text.replace(old_nginx, new_nginx)

# 3. 规范化节点名称
old_url_txt = """    cat > ${work_dir}/url.txt << EOF
vless://${uuid}@${server_ip}:${vless_port}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=firefox&pbk=${public_key}&type=tcp&headerType=none#${isp}

vmess://$(echo "$VMESS" | base64 -w0)

hysteria2://${uuid}@${server_ip}:${hy2_port}/?sni=www.bing.com&insecure=1&pinSHA256=${fingerprint}&alpn=h3&obfs=none#${isp}

tuic://${uuid}:${uuid}@${server_ip}:${tuic_port}?sni=www.bing.com&congestion_control=bbr&udp_relay_mode=native&alpn=h3&allow_insecure=1#${isp}
EOF"""

new_url_txt = """    cat > ${work_dir}/url.txt << EOF
vless://${uuid}@${server_ip}:${vless_port}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=firefox&pbk=${public_key}&type=tcp&headerType=none#${isp}-Reality

vmess://$(echo "$VMESS" | jq -c '.ps = "'"${isp}"'-Argo"' | base64 -w0)

hysteria2://${uuid}@${server_ip}:${hy2_port}/?sni=www.bing.com&insecure=1&pinSHA256=${fingerprint}&alpn=h3&obfs=none#${isp}-Hy2

tuic://${uuid}:${uuid}@${server_ip}:${tuic_port}?sni=www.bing.com&congestion_control=bbr&udp_relay_mode=native&alpn=h3&allow_insecure=1#${isp}-Tuic
EOF"""
if old_url_txt in text:
    text = text.replace(old_url_txt, new_url_txt)

# 4. 优化 change_argo_domain
old_change_argo = """    updated_vmess=$(echo "$decoded_vmess" | jq --arg new_domain "$ArgoDomain" '.host = $new_domain | .sni = $new_domain')"""
new_change_argo = """    updated_vmess=$(echo "$decoded_vmess" | jq --arg new_domain "$ArgoDomain" '.host = $new_domain | .sni = $new_domain | if (.ps | endswith("-Argo") | not) then .ps += "-Argo" else . end')"""
if old_change_argo in text:
    text = text.replace(old_change_argo, new_change_argo)

# 5. 注入 argo-watch (openrc)
old_openrc = """    chmod +x /etc/init.d/sing-box
    chmod +x /etc/init.d/argo
    rc-update add sing-box default > /dev/null 2>&1
    rc-update add argo default     > /dev/null 2>&1
}"""

new_openrc = """    # 注入 argo-watch 自动化域名守护服务
    cat > /etc/sing-box/update_argo_sub.sh << 'SUB_EOF'
#!/bin/sh
log_file="/etc/sing-box/argo.log"
url_file="/etc/sing-box/url.txt"
sub_file="/etc/sing-box/sub.txt"

[ -f "$log_file" ] || exit 0
[ -f "$url_file" ] || exit 0

new_domain=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$log_file" | tail -n 1 | sed 's@https://@@')
[ -n "$new_domain" ] || exit 0

vmess_url=$(grep -o 'vmess://[^ ]*' "$url_file")
[ -n "$vmess_url" ] || exit 0

encoded_vmess="${vmess_url#vmess://}"
decoded_vmess=$(echo "$encoded_vmess" | base64 -d 2>/dev/null)
current_domain=$(echo "$decoded_vmess" | jq -r '.host // empty')

if [ "$new_domain" != "$current_domain" ]; then
    updated_vmess=$(echo "$decoded_vmess" | jq --arg d "$new_domain" '.host = $d | .sni = $d | if (.ps | endswith("-Argo") | not) then .ps += "-Argo" else . end')
    encoded_updated_vmess=$(echo "$updated_vmess" | base64 | tr -d '\r\n')
    sed -i "s|$vmess_url|vmess://${encoded_updated_vmess}|" "$url_file"
    base64 -w0 "$url_file" > "$sub_file"
    chmod 644 "$sub_file"
fi
SUB_EOF
    chmod +x /etc/sing-box/update_argo_sub.sh

    cat > /etc/sing-box/argo_daemon.sh << 'DAEMON_EOF'
#!/bin/sh
while true; do
    /etc/sing-box/update_argo_sub.sh >/dev/null 2>&1
    sleep 30
done
DAEMON_EOF
    chmod +x /etc/sing-box/argo_daemon.sh

    cat > /etc/init.d/argo-watch << 'WATCH_EOF'
#!/sbin/openrc-run
description="Auto sync Argo domain to subscription"
command="/etc/sing-box/argo_daemon.sh"
command_background=true
pidfile="/var/run/argo-watch.pid"

depend() {
    need argo
}
WATCH_EOF
    chmod +x /etc/init.d/argo-watch

    chmod +x /etc/init.d/sing-box
    chmod +x /etc/init.d/argo
    rc-update add sing-box default   > /dev/null 2>&1
    rc-update add argo default       > /dev/null 2>&1
    rc-update add argo-watch default > /dev/null 2>&1
    rc-update add nginx default      > /dev/null 2>&1
    rc-service argo-watch start      > /dev/null 2>&1 || true
}"""
if old_openrc in text:
    text = text.replace(old_openrc, new_openrc)

# 6. 注入 argo-watch (systemd)
old_systemd = """    systemctl daemon-reload
    systemctl enable sing-box
    systemctl start sing-box
    systemctl enable argo
    systemctl start argo
}"""

new_systemd = """    # 注入 argo-watch 自动化域名守护服务 (systemd)
    cat > /etc/sing-box/update_argo_sub.sh << 'SUB_EOF'
#!/bin/sh
log_file="/etc/sing-box/argo.log"
url_file="/etc/sing-box/url.txt"
sub_file="/etc/sing-box/sub.txt"

[ -f "$log_file" ] || exit 0
[ -f "$url_file" ] || exit 0

new_domain=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$log_file" | tail -n 1 | sed 's@https://@@')
[ -n "$new_domain" ] || exit 0

vmess_url=$(grep -o 'vmess://[^ ]*' "$url_file")
[ -n "$vmess_url" ] || exit 0

encoded_vmess="${vmess_url#vmess://}"
decoded_vmess=$(echo "$encoded_vmess" | base64 -d 2>/dev/null)
current_domain=$(echo "$decoded_vmess" | jq -r '.host // empty')

if [ "$new_domain" != "$current_domain" ]; then
    updated_vmess=$(echo "$decoded_vmess" | jq --arg d "$new_domain" '.host = $d | .sni = $d | if (.ps | endswith("-Argo") | not) then .ps += "-Argo" else . end')
    encoded_updated_vmess=$(echo "$updated_vmess" | base64 | tr -d '\r\n')
    sed -i "s|$vmess_url|vmess://${encoded_updated_vmess}|" "$url_file"
 
