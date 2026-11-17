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

# 1. Update shortcut
text = text.replace(
    'https://raw.githubusercontent.com/eooce/sing-box/main/sing-box.sh',
    'https://raw.githubusercontent.com/shadowxhero/Sing-box/main/sing-box.sh'
)

# 2. Nginx 404
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
text = text.replace(old_nginx, new_nginx)

# 3. Strip ports
old_ports = """    nginx_port=$(($vless_port + 1))
    tuic_port=$(($vless_port + 2))
    hy2_port=$(($vless_port + 3))
    uuid=$(cat /proc/sys/kernel/random/uuid)
    password=$(< /dev/urandom tr -dc 'A-Za-z0-9' | head -c 24)
    output=$(/etc/sing-box/sing-box generate reality-keypair)
    private_key=$(echo "${output}" | awk '/PrivateKey:/ {print $2}')
    public_key=$(echo "${output}" | awk '/PublicKey:/ {print $2}')

    allow_port $vless_port/tcp $nginx_port/tcp $tuic_port/udp $hy2_port/udp > /dev/null 2>&1"""
new_ports = """    nginx_port=$(($vless_port + 1))
    uuid=$(cat /proc/sys/kernel/random/uuid)
    password=$(< /dev/urandom tr -dc 'A-Za-z0-9' | head -c 24)
    output=$(/etc/sing-box/sing-box generate reality-keypair)
    private_key=$(echo "${output}" | awk '/PrivateKey:/ {print $2}')
    public_key=$(echo "${output}" | awk '/PublicKey:/ {print $2}')

    allow_port $vless_port/tcp $nginx_port/tcp > /dev/null 2>&1"""
text = text.replace(old_ports, new_ports)
# 4. inbounds.json
old_inbounds = """      "transport": {
        "type": "ws",
        "path": "/vmess-argo",
        "early_data_header_name": "Sec-WebSocket-Protocol"
      }
    },
    {
      "type": "hysteria2",
      "tag": "hysteria2",
      "listen": "::",
      "listen_port": $hy2_port,
      "users": [
        {
          "password": "$uuid"
        }
      ],
      "ignore_client_bandwidth": false,
      "masquerade": "https://bing.com",
      "tls": {
        "enabled": true,
        "alpn": ["h3"],
        "min_version": "1.3",
        "max_version": "1.3",
        "certificate_path": "$work_dir/cert.pem",
        "key_path": "$work_dir/private.key"
      }
    },
    {
      "type": "tuic",
      "tag": "tuic",
      "listen": "::",
      "listen_port": $tuic_port,
      "users": [
        {
          "uuid": "$uuid",
          "password": "$uuid"
        }
      ],
      "congestion_control": "bbr",
      "tls": {
        "enabled": true,
        "alpn": ["h3"],
        "certificate_path": "$work_dir/cert.pem",
        "key_path": "$work_dir/private.key"
      }
    }
  ]
}
EOF"""
new_inbounds = """      "transport": {
        "type": "ws",
        "path": "/vmess-argo",
        "early_data_header_name": "Sec-WebSocket-Protocol"
      }
    }
  ]
}
EOF"""
text = text.replace(old_inbounds, new_inbounds)
# 5. url.txt
old_url_txt = """    cat > ${work_dir}/url.txt << EOF
vless://${uuid}@${server_ip}:${vless_port}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=firefox&pbk=${public_key}&type=tcp&headerType=none#${isp}

vmess://$(echo "$VMESS" | base64 -w0)

hysteria2://${uuid}@${server_ip}:${hy2_port}/?sni=www.bing.com&insecure=1&pinSHA256=${fingerprint}&alpn=h3&obfs=none#${isp}

tuic://${uuid}:${uuid}@${server_ip}:${tuic_port}?sni=www.bing.com&congestion_control=bbr&udp_relay_mode=native&alpn=h3&allow_insecure=1#${isp}
EOF"""
new_url_txt = """    cat > ${work_dir}/url.txt << EOF
vless://${uuid}@${server_ip}:${vless_port}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.iij.ad.jp&fp=firefox&pbk=${public_key}&type=tcp&headerType=none#${isp}-Reality

vmess://$(echo "$VMESS" | jq -c '.ps = "'"${isp}"'-Argo"' | base64 -w0)
EOF"""
text = text.replace(old_url_txt, new_url_txt)

# 6. change_argo_domain
old_change_argo = """    updated_vmess=$(echo "$decoded_vmess" | jq --arg new_domain "$ArgoDomain" '.host = $new_domain | .sni = $new_domain')"""
new_change_argo = """    updated_vmess=$(echo "$decoded_vmess" | jq --arg new_domain "$ArgoDomain" '.host = $new_domain | .sni = $new_domain | if (.ps | endswith("-Argo") | not) then .ps += "-Argo" else . end')"""
text = text.replace(old_change_argo, new_change_argo)
# 7.4 openrc argo 内存锁
old_openrc_argo = """    cat > /etc/init.d/argo << 'EOF'
#!/sbin/openrc-run
description="Cloudflare Tunnel"
command="/bin/sh"
command_args="-c '/etc/sing-box/argo tunnel --url http://localhost:8001 --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1'"
command_background=true
pidfile="/var/run/argo.pid"
EOF"""

new_openrc_argo = """    cat > /etc/init.d/argo << 'EOF'
#!/sbin/openrc-run
description="Cloudflare Tunnel"
export GOMEMLIMIT=30MiB
export GOGC=25
command="/bin/sh"
command_args="-c 'exec /etc/sing-box/argo tunnel --url http://localhost:8001 --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1'"
command_background=true
pidfile="/var/run/argo.pid"

start_pre() {
    rm -f /var/run/argo.pid /run/argo.pid
}
EOF"""
if old_openrc_argo in text:
    text = text.replace(old_openrc_argo, new_openrc_argo)

# 7.1 openrc 注入内存锁
old_openrc_init = """    cat > /etc/init.d/sing-box << 'EOF'
#!/sbin/openrc-run
description="sing-box service"
command="/etc/sing-box/sing-box"
command_args="run -C /etc/sing-box/conf"
command_background=true
pidfile="/var/run/sing-box.pid"
EOF"""

new_openrc_init = """    cat > /etc/init.d/sing-box << 'EOF'
#!/sbin/openrc-run
description="sing-box service"
export GOMEMLIMIT=48MiB
export GOGC=30
command="/etc/sing-box/sing-box"
command_args="run -C /etc/sing-box/conf"
command_background=true
pidfile="/var/run/sing-box.pid"
EOF"""
if old_openrc_init in text:
    text = text.replace(old_openrc_init, new_openrc_init)

# 7.2 openrc
old_openrc = """    chmod +x /etc/init.d/sing-box
    chmod +x /etc/init.d/argo
    rc-update add sing-box default > /dev/null 2>&1
    rc-update add argo default     > /dev/null 2>&1
}"""
new_openrc = """    cat > /etc/sing-box/update_argo_sub.sh << 'SUB_EOF'
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
    if ! pgrep -f "/etc/sing-box/sing-box run" >/dev/null 2>&1; then
        rc-service sing-box stop >/dev/null 2>&1
        rc-service sing-box start >/dev/null 2>&1
    fi
    if ! pgrep -f "/etc/sing-box/argo tunnel" >/dev/null 2>&1; then
        rc-service argo stop >/dev/null 2>&1
        rc-service argo start >/dev/null 2>&1
        sleep 5
    fi
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
    after argo sing-box
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
text = text.replace(old_openrc, new_openrc)
# 7.3 systemd argo 内存锁
old_systemd_argo = """[Service]
Type=simple
NoNewPrivileges=yes
TimeoutStartSec=0
ExecStart=/bin/sh -c "/etc/sing-box/argo tunnel --url http://localhost:8001 --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1"
Restart=on-failure
RestartSec=5s"""

new_systemd_argo = """[Service]
Type=simple
NoNewPrivileges=yes
TimeoutStartSec=0
Environment="GOMEMLIMIT=30MiB" "GOGC=25"
ExecStart=/bin/sh -c "/etc/sing-box/argo tunnel --url http://localhost:8001 --no-autoupdate --edge-ip-version auto --protocol http2 > /etc/sing-box/argo.log 2>&1"
Restart=on-failure
RestartSec=5s"""
if old_systemd_argo in text:
    text = text.replace(old_systemd_argo, new_systemd_argo)

# 8.1 systemd 注入内存锁
old_systemd_singbox = """ExecStart=/etc/sing-box/sing-box run -C /etc/sing-box/conf
ExecReload=/bin/kill -HUP \$MAINPID"""

new_systemd_singbox = """Environment="GOMEMLIMIT=48MiB" "GOGC=30"
ExecStart=/etc/sing-box/sing-box run -C /etc/sing-box/conf
ExecReload=/bin/kill -HUP \$MAINPID"""
if old_systemd_singbox in text:
    text = text.replace(old_systemd_singbox, new_systemd_singbox)

# 8.2 systemd
old_systemd = """    systemctl daemon-reload
    systemctl enable sing-box
    systemctl start sing-box
    systemctl enable argo
    systemctl start argo
}"""
new_systemd = """    cat > /etc/sing-box/update_argo_sub.sh << 'SUB_EOF'
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

    cat > /etc/systemd/system/argo-watch.service << 'WATCH_EOF'
[Unit]
Description=Auto sync Argo domain to subscription & keep services alive
After=argo.service sing-box.service

[Service]
Type=simple
ExecStart=/bin/sh -c 'while true; do pgrep -f "/etc/sing-box/sing-box run" >/dev/null 2>&1 || systemctl restart sing-box; pgrep -f "/etc/sing-box/argo tunnel" >/dev/null 2>&1 || systemctl restart argo; /etc/sing-box/update_argo_sub.sh >/dev/null 2>&1; sleep 30; done'
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
WATCH_EOF

    systemctl daemon-reload
    systemctl enable sing-box
    systemctl start sing-box
    systemctl enable argo
    systemctl start argo
    systemctl enable argo-watch >/dev/null 2>&1 || true
    systemctl start argo-watch  >/dev/null 2>&1 || true
    systemctl enable nginx      >/dev/null 2>&1 || true
}"""
text = text.replace(old_systemd, new_systemd)

# 9. 修复更换订阅端口时在 Alpine (BusyBox lsof) 下的误报死循环
old_check_port = """            until [[ -z $(lsof -iTCP:"$sub_port" -sTCP:LISTEN -t) ]]; do"""
new_check_port = """            until ! (ss -tln 2>/dev/null | grep -q -E ":${sub_port}[[:space:]]" || (command -v netstat &>/dev/null && netstat -tln 2>/dev/null | grep -q -E ":${sub_port}[[:space:]]")); do"""
if old_check_port in text:
    text = text.replace(old_check_port, new_check_port)

# 10. 菜单补回的 Hysteria2 属于额外节点，刷新订阅时不能按基础节点丢弃
old_extra_filter = """        extra_lines=$(grep -vE '^(vless://|vmess://|hysteria2://|tuic://)' \"${client_dir}\" || true)"""
new_extra_filter = """        extra_lines=$(grep -vE '^(vless://|vmess://|tuic://)' \"${client_dir}\" || true)"""
if old_extra_filter not in text:
    sys.exit("订阅额外节点过滤锚点未找到，上游可能已改动")
text = text.replace(old_extra_filter, new_extra_filter)

# 11. 协议管理菜单补回 Hysteria2（默认安装已剥离，改由菜单按需添加）
old_proto_menu = """    green "--- Shadowsocks-2022 协议 ---"
    green "5. 添加 Shadowsocks-2022 协议"
    red   "6. 删除 Shadowsocks-2022 协议"
    skyblue "-----------------------------"
    purple "0. 返回主菜单"
    skyblue "-----------------------------"
    reading "请输入选择: " proto_choice
    echo ""
    case "${proto_choice}" in
        1) add_socks5_inbound ;;
        2) remove_socks5_inbound ;;
        3) add_anytls ;;
        4) remove_anytls ;;
        5) add_ss2022 ;;
        6) remove_ss2022 ;;
        0) menu; return ;;
        *) red "无效的选项！" ;;
    esac"""
new_proto_menu = """    green "--- Shadowsocks-2022 协议 ---"
    green "5. 添加 Shadowsocks-2022 协议"
    red   "6. 删除 Shadowsocks-2022 协议"
    skyblue "-----------------------------"
    green "--- Hysteria2 协议 ---"
    green "7. 添加 Hysteria2 协议"
    red   "8. 删除 Hysteria2 协议"
    skyblue "-----------------------------"
    purple "0. 返回主菜单"
    skyblue "-----------------------------"
    reading "请输入选择: " proto_choice
    echo ""
    case "${proto_choice}" in
        1) add_socks5_inbound ;;
        2) remove_socks5_inbound ;;
        3) add_anytls ;;
        4) remove_anytls ;;
        5) add_ss2022 ;;
        6) remove_ss2022 ;;
        7) add_hysteria2 ;;
        8) remove_hysteria2 ;;
        0) menu; return ;;
        *) red "无效的选项！" ;;
    esac"""
if old_proto_menu not in text:
    sys.exit("协议管理菜单锚点未找到，上游可能已改动")
text = text.replace(old_proto_menu, new_proto_menu)

old_proto_status = """        echo -e " Shadowsocks-2022: ${yellow}未启用${re}"
    fi
    echo ""
}"""
new_proto_status = """        echo -e " Shadowsocks-2022: ${yellow}未启用${re}"
    fi

    # Hysteria2
    if jq -e '.inbounds[] | select(.tag == "hysteria2")' "$inbounds_file" > /dev/null 2>&1; then
        local hy_port
        hy_port=$(jq -r '.inbounds[] | select(.tag == "hysteria2") | .listen_port' "$inbounds_file")
        echo -e " Hysteria2:        ${green}已启用${re} (端口: ${skyblue}${hy_port}${re}/udp)"
    else
        echo -e " Hysteria2:        ${yellow}未启用${re}"
    fi
    echo ""
}"""
if old_proto_status not in text:
    sys.exit("额外协议状态锚点未找到，上游可能已改动")
text = text.replace(old_proto_status, new_proto_status)

old_remove_ss = """    green "\\nShadowsocks-2022 协议已删除\\n"
}"""
new_remove_ss = """    green "\\nShadowsocks-2022 协议已删除\\n"
}

# ---- Hysteria2 ----
add_hysteria2() {
    local inbounds_file="${conf_dir}/inbounds.json"
    local tag="hysteria2"

    if proto_exists "$tag"; then
        yellow "Hysteria2 协议已存在，无需重复添加。"; sleep 1; return
    fi

    local current_uuid
    current_uuid=$(get_current_uuid)
    if [ -z "$current_uuid" ]; then
        red "无法获取当前UUID，请确认 sing-box 已正确安装并配置。"; sleep 2; return
    fi

    if [ ! -f "${work_dir}/cert.pem" ] || [ ! -f "${work_dir}/private.key" ]; then
        openssl ecparam -genkey -name prime256v1 -out "${work_dir}/private.key"
        openssl req -new -x509 -days 3650 -key "${work_dir}/private.key" -out "${work_dir}/cert.pem" -subj "/CN=bing.com"
    fi
    local fingerprint
    fingerprint=$(openssl x509 -noout -fingerprint -sha256 -in "${work_dir}/cert.pem" | cut -d'=' -f2 | sed 's/:/%3A/g')

    while true; do
        reading "请输入 Hysteria2 监听端口 (回车随机生成): " hy_port
        if [ -z "$hy_port" ]; then
            hy_port=$(shuf -i 10000-65000 -n 1)
            green "Hysteria2监听端口：${purple}${hy_port}${re}"
            break
        fi
        if [[ ! "$hy_port" =~ ^[0-9]+$ ]] || [ "$hy_port" -gt 65535 ] || [ "$hy_port" -lt 1 ]; then
            yellow "错误：端口必须是1-65535之间的数字！"
            continue
        fi
        green "Hysteria2监听端口：${purple}${hy_port}${re}"
        break
    done

    jq --arg tag "$tag" \\
       --argjson port "$hy_port" \\
       --arg pass "$current_uuid" \\
       --arg cert "${work_dir}/cert.pem" \\
       --arg key "${work_dir}/private.key" \\
       '.inbounds += [{
           "type": "hysteria2",
           "tag": $tag,
           "listen": "::",
           "listen_port": $port,
           "users": [{"password": $pass}],
           "ignore_client_bandwidth": false,
           "masquerade": "https://bing.com",
           "tls": {
               "enabled": true,
               "alpn": ["h3"],
               "min_version": "1.3",
               "max_version": "1.3",
               "certificate_path": $cert,
               "key_path": $key
           }
       }]' "$inbounds_file" > "${inbounds_file}.tmp" && mv "${inbounds_file}.tmp" "$inbounds_file"

    allow_port ${hy_port}/udp > /dev/null 2>&1

    local server_ip
    server_ip=$(get_realip)
    local isp
    isp=$(curl -sm 3 -H "User-Agent: Mozilla/5.0" "https://api.ip.sb/geoip" | tr -d '\\n' \\
        | awk -F\\" '{c="";i="";for(x=1;x<=NF;x++){if($x=="country_code")c=$(x+2);if($x=="isp")i=$(x+2)};if(c&&i)print c"-"i}' \\
        | sed 's/ /_/g' || echo "Hy2")

    local url_line="hysteria2://${current_uuid}@${server_ip}:${hy_port}/?sni=www.bing.com&insecure=1&pinSHA256=${fingerprint}&alpn=h3&obfs=none#${isp}-Hy2"

    echo "" >> "${client_dir}"
    echo "${url_line}" >> "${client_dir}"
    update_sub

    restart_singbox

    green "\\nHysteria2 协议已添加！"
    green "密码(UUID): ${purple}${current_uuid}${re}"
    green "端口: ${purple}${hy_port}${re}/udp"
    green "节点链接:\\n${purple}${url_line}${re}\\n"
    yellow "如果节点不通，请在客户端将 \\"跳过证书验证\\" 设置为 true 或切换内核"
    [ -x "${work_dir}/qrencode" ] && "${work_dir}/qrencode" "$url_line"
}

remove_hysteria2() {
    local inbounds_file="${conf_dir}/inbounds.json"
    local tag="hysteria2"

    if ! proto_exists "$tag"; then
        yellow "Hysteria2 协议未添加，无需删除。"; sleep 1; return
    fi

    jq --arg tag "$tag" 'del(.inbounds[] | select(.tag == $tag))' \\
        "$inbounds_file" > "${inbounds_file}.tmp" && mv "${inbounds_file}.tmp" "$inbounds_file"

    remove_url_by_tag "hysteria2"
    update_sub
    restart_singbox
    green "\\nHysteria2 协议已删除\\n"
}"""
if old_remove_ss not in text:
    sys.exit("Shadowsocks 删除函数锚点未找到，上游可能已改动")
text = text.replace(old_remove_ss, new_remove_ss)

with open("sing-box.sh", "w", encoding="utf-8", newline="\n") as f:
    f.write(text)

print("Patching completed successfully!")
