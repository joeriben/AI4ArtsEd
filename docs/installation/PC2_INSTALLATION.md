# PC2 Headless Server — Vollstaendige Installation

**Ziel:** PC2 als Primary Headless Server einrichten via 4TB Offline-Installationsmedium.
**Gesteuert von:** Claude Code auf PC2
**Erstellt:** 2026-02-23

---

## PC2 Spezifikationen

| | PC2 | PC1 (Referenz) |
|---|---|---|
| **User** | `ai4artsed` | `joerissen` |
| **GPU** | RTX 6000 Blackwell (96GB VRAM) | RTX 6000 Blackwell (96GB VRAM) |
| **RAM** | 128 GB | 64 GB |
| **OS** | Fedora 42 | Fedora 42 |
| **Rolle** | Primary Server | Secondary/Backup |
| **Tunnel** | `werkraum-tunnel-pc2` | `werkraum-tunnel` |
| **Hostnames** | `lab2.ai4artsed.org`, `ssh-pc2.ai4artsed.org` | `lab.ai4artsed.org`, `ssh-fedora.ai4artsed.org` |
| **Netzwerk** | WiFi zum 5G-Router | WiFi / Ethernet |

## Port-Belegung

| Port | Service |
|------|---------|
| 22 | SSH (via Cloudflare Tunnel) |
| 5174 | Frontend (npx serve, built Vue) |
| 11434 | Ollama |
| 17801 | Production Backend (Flask) |
| 17803 | GPU Service (Diffusers + HeartMuLa) |

## Verzeichnisstruktur

```
/home/ai4artsed/ai/
  ai4artsed_development/     <- develop branch, Port 17802 (dev)
  ai4artsed_production/      <- main branch, Port 17801 (prod)
  heartlib/                  <- HeartMuLa (pip install -e)
  ImageBind/                 <- ImageBind (pip install -e)
  MMAudio/                   <- MMAudio (pip install -e)
  SwarmUI/                   <- ComfyUI backend
```

---

## Installation (Reihenfolge einhalten!)

### Phase 1: HD mounten und System pruefen

```bash
# HD identifizieren und mounten
lsblk
sudo mount /dev/sdX1 /mnt/install-drive
ls /mnt/install-drive/

# System-Info sammeln
uname -a
free -h
nvidia-smi
ip link show
nmcli connection show
systemctl list-unit-files --state=enabled | grep -E "(cloud|ai4|ollama|gdm|nvidia)"
```

### Phase 2: System-Pakete installieren

```bash
# Cloudflared
sudo rpm -i /mnt/install-drive/installers/cloudflared-linux-amd64.rpm

# Ollama
bash /mnt/install-drive/installers/ollama-install.sh

# System-Dependencies (WeasyPrint etc.)
sudo dnf install --disablerepo='*' /mnt/install-drive/system-deps/*.rpm

# Node.js (falls nicht vorhanden)
if ! command -v node &>/dev/null; then
  sudo tar -xJf /mnt/install-drive/installers/node-v22.22.0-linux-x64.tar.xz \
    -C /usr/local --strip-components=1
fi
```

### Phase 3: Repos einrichten

```bash
mkdir -p /home/ai4artsed/ai

# Development (develop branch)
git clone /mnt/install-drive/repos/ai4artsed.git /home/ai4artsed/ai/ai4artsed_development
cd /home/ai4artsed/ai/ai4artsed_development && git checkout develop

# Production (main branch)
git clone /mnt/install-drive/repos/ai4artsed.git /home/ai4artsed/ai/ai4artsed_production
cd /home/ai4artsed/ai/ai4artsed_production && git checkout main

# heartlib, ImageBind, MMAudio
cp -r /mnt/install-drive/repos/heartlib /home/ai4artsed/ai/heartlib
cp -r /mnt/install-drive/repos/ImageBind /home/ai4artsed/ai/ImageBind
cp -r /mnt/install-drive/repos/MMAudio /home/ai4artsed/ai/MMAudio
```

### Phase 4: Python venvs (offline aus pip-cache)

```bash
# Development venv
cd /home/ai4artsed/ai/ai4artsed_development
python3 -m venv venv

# PyTorch zuerst (CUDA 13.0 nightly fuer Blackwell)
venv/bin/pip install --no-index --find-links=/mnt/install-drive/pip-cache/torch-nightly/ \
  torch torchaudio torchvision

# Dann requirements.txt
venv/bin/pip install --no-index --find-links=/mnt/install-drive/pip-cache/ \
  -r requirements.txt

# SpaCy Modelle
venv/bin/pip install --no-index --find-links=/mnt/install-drive/pip-cache/spacy-models/ \
  de_core_news_lg xx_ent_wiki_sm

# Editable installs
venv/bin/pip install --no-deps -e /home/ai4artsed/ai/heartlib
venv/bin/pip install --no-deps -e /home/ai4artsed/ai/ImageBind
venv/bin/pip install --no-deps -e /home/ai4artsed/ai/MMAudio

# Production venv (gleiche Packages)
cd /home/ai4artsed/ai/ai4artsed_production
python3 -m venv venv
venv/bin/pip install --no-index --find-links=/mnt/install-drive/pip-cache/torch-nightly/ \
  torch torchaudio torchvision
venv/bin/pip install --no-index --find-links=/mnt/install-drive/pip-cache/ \
  -r requirements.txt
venv/bin/pip install --no-index --find-links=/mnt/install-drive/pip-cache/spacy-models/ \
  de_core_news_lg xx_ent_wiki_sm
```

### Phase 5: Frontend bauen

```bash
cd /home/ai4artsed/ai/ai4artsed_production/public/ai4artsed-frontend
# Falls npm-cache vorhanden:
rsync -av /mnt/install-drive/npm-cache/node_modules/ ./node_modules/
npm run build

# Falls kein npm-cache: npm install braucht Internet
```

### Phase 6: AI Modelle platzieren

```bash
# Ollama Modelle
sudo systemctl start ollama
sudo rsync -av /mnt/install-drive/models/ollama/ /usr/share/ollama/.ollama/models/
sudo chown -R ollama:ollama /usr/share/ollama/.ollama/models/
sudo systemctl restart ollama
ollama list  # Verifizieren: llama-guard3:1b, qwen3:1.7b, qwen3-vl:2b, qwen3:4b, llama3.2-vision

# HuggingFace Cache (direkt portabel)
mkdir -p /home/ai4artsed/.cache/huggingface/hub
rsync -av /mnt/install-drive/models/huggingface/ /home/ai4artsed/.cache/huggingface/hub/

# Extra Diffusers Caches
mkdir -p /home/ai4artsed/ai/models/diffusers /home/ai4artsed/ai/diffusers_cache
rsync -av /mnt/install-drive/models/diffusers-extra/ /home/ai4artsed/ai/models/diffusers/
rsync -av /mnt/install-drive/models/diffusers-cache-extra/ /home/ai4artsed/ai/diffusers_cache/

# GPU Service Weights
rsync -av /mnt/install-drive/models/gpu-service-weights/weights/ \
  /home/ai4artsed/ai/ai4artsed_development/gpu_service/weights/
rsync -av /mnt/install-drive/models/gpu-service-weights/ext_weights/ \
  /home/ai4artsed/ai/ai4artsed_development/gpu_service/ext_weights/

# SwarmUI/ComfyUI Modelle
mkdir -p /home/ai4artsed/ai/SwarmUI/Models
rsync -av /mnt/install-drive/models/swarmui/ /home/ai4artsed/ai/SwarmUI/Models/
```

---

## Headless Server Konfiguration

### Phase 7: NVIDIA Persistence

**MUSS vor GDM-Deaktivierung laufen!** Ohne dies crasht die GPU wenn GDM weg ist.

```bash
sudo tee /etc/systemd/system/nvidia-persistenced.service << 'EOF'
[Unit]
Description=NVIDIA Persistence Daemon
Before=ollama.service ai4artsed-gpu.service ai4artsed-production.service

[Service]
Type=forking
ExecStart=/usr/bin/nvidia-persistenced --user ai4artsed --no-persistence-mode-reset
ExecStopPost=/usr/bin/nvidia-smi -pm 0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now nvidia-persistenced
nvidia-smi -q | grep -i persistence  # Muss "Enabled" zeigen
```

### Phase 8: Cloudflare Tunnel

```bash
# Setup-Script (erfordert Browser-Login — einmalig vor Ort)
cp /mnt/install-drive/scripts/setup_cloudflared_pc2.sh ~/
cp /mnt/install-drive/scripts/6_*.sh ~/
bash ~/setup_cloudflared_pc2.sh

# config.yml fuer systemd
sudo mkdir -p /etc/cloudflared
TUNNEL_UUID=$(ls ~/.cloudflared/*.json | head -1 | xargs basename | sed 's/.json//')

sudo tee /etc/cloudflared/config.yml << EOF
tunnel: werkraum-tunnel-pc2
credentials-file: /home/ai4artsed/.cloudflared/${TUNNEL_UUID}.json

ingress:
  - hostname: lab2.ai4artsed.org
    service: http://127.0.0.1:17801
    originRequest:
      httpHostHeader: lab2.ai4artsed.org
      connectTimeout: 60s
      tcpKeepAlive: 30s
      keepAliveConnections: 100
      keepAliveTimeout: 90s

  - hostname: ssh-pc2.ai4artsed.org
    service: ssh://localhost:22

  - service: http_status:404
EOF

sudo tee /etc/systemd/system/cloudflared.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel - werkraum-tunnel-pc2
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
TimeoutStartSec=0
ExecStart=/usr/local/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
```

### Phase 9: systemd Service Units

```bash
# GPU Service (Port 17803)
sudo tee /etc/systemd/system/ai4artsed-gpu.service << 'EOF'
[Unit]
Description=AI4ArtsEd GPU Service (port 17803)
After=network.target nvidia-persistenced.service
Requires=nvidia-persistenced.service

[Service]
Type=simple
User=ai4artsed
WorkingDirectory=/home/ai4artsed/ai/ai4artsed_development/gpu_service
Environment="GPU_SERVICE_PORT=17803"
Environment="AI_TOOLS_BASE=/home/ai4artsed/ai"
Environment="HOME=/home/ai4artsed"
Environment="PATH=/home/ai4artsed/ai/ai4artsed_development/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ai4artsed/ai/ai4artsed_development/venv/bin/python server.py
Restart=on-failure
RestartSec=30
TimeoutStartSec=300
StartLimitIntervalSec=600
StartLimitBurst=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Production Backend (Port 17801)
sudo tee /etc/systemd/system/ai4artsed-production.service << 'EOF'
[Unit]
Description=AI4ArtsEd Production Backend (port 17801)
After=network-online.target ollama.service nvidia-persistenced.service
Wants=network-online.target

[Service]
Type=simple
User=ai4artsed
WorkingDirectory=/home/ai4artsed/ai/ai4artsed_production/devserver
Environment="PORT=17801"
Environment="DISABLE_API_CACHE=false"
Environment="AI_TOOLS_BASE=/home/ai4artsed/ai"
Environment="HOME=/home/ai4artsed"
Environment="PATH=/home/ai4artsed/ai/ai4artsed_production/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ai4artsed/ai/ai4artsed_production/venv/bin/python server.py
Restart=on-failure
RestartSec=15
StartLimitIntervalSec=300
StartLimitBurst=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Frontend (Port 5174)
sudo tee /etc/systemd/system/lab-frontend.service << 'EOF'
[Unit]
Description=AI4ArtsEd Frontend (port 5174)
After=network.target

[Service]
Type=simple
User=ai4artsed
WorkingDirectory=/home/ai4artsed/ai/ai4artsed_production/public/ai4artsed-frontend
ExecStart=/usr/bin/npx serve -s dist -l 5174
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Ollama GPU Drop-in
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/gpu.conf << 'EOF'
[Service]
Environment="OLLAMA_NUM_GPU=-1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF

# Alles enablen
sudo systemctl daemon-reload
sudo systemctl enable nvidia-persistenced cloudflared ollama \
  ai4artsed-gpu ai4artsed-production lab-frontend
```

### Phase 10: Sicherheit

```bash
# SSH Haertung
sudo cp /mnt/install-drive/configs/ssh/99-hardening.conf /etc/ssh/sshd_config.d/
sudo systemctl restart sshd

# Firewall haerten (Fedora-Default hat 1025-65535 offen!)
sudo firewall-cmd --permanent --zone=FedoraWorkstation --remove-port=1025-65535/tcp
sudo firewall-cmd --permanent --zone=FedoraWorkstation --remove-port=1025-65535/udp
sudo firewall-cmd --permanent --zone=FedoraWorkstation --remove-service=samba
sudo firewall-cmd --permanent --zone=FedoraWorkstation --remove-service=samba-client
sudo firewall-cmd --permanent --zone=FedoraWorkstation --remove-service=mdns
sudo firewall-cmd --permanent --zone=FedoraWorkstation --add-service=ssh
sudo firewall-cmd --reload
```

### Phase 11: Headless-Umstellung + Auto-Recovery

```bash
# GDM deaktivieren (NACH nvidia-persistenced!)
sudo systemctl set-default multi-user.target
sudo systemctl disable gdm.service

# GRUB: graphical splash entfernen
sudo sed -i 's/ rhgb//' /etc/default/grub
sudo grub2-mkconfig -o /boot/grub2/grub.cfg

# Hardware Watchdog (iTCO_wdt) aktivieren
# In /etc/systemd/system.conf unter [Manager] hinzufuegen:
#   RuntimeWatchdogSec=30s
#   RebootWatchdogSec=10min
#   WatchdogDevice=/dev/watchdog
sudo systemctl daemon-reexec
```

### Phase 12: 5G WiFi

```bash
# SSID + Passwort vor Ort eintragen!
sudo nmcli connection add \
  type wifi \
  con-name "5G-Router" \
  ssid "MEINE-5G-SSID" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "MEIN-PASSWORT" \
  connection.autoconnect yes \
  connection.autoconnect-priority 100 \
  ipv4.method auto

# Andere WiFi-Verbindungen auf auto-connect=no setzen
# nmcli connection show  (zeigt alle, dann fuer jede:)
# sudo nmcli connection modify "NAME" connection.autoconnect no
```

### Phase 13: BIOS (in Person)

- **Power On After AC Loss** = ON
- Delete/F2 beim Booten, unter Advanced / ACPI / Power Settings

---

## Verifikation

```bash
# Alle Services starten
sudo systemctl start nvidia-persistenced cloudflared ollama \
  ai4artsed-gpu ai4artsed-production lab-frontend

# Status pruefen
systemctl status nvidia-persistenced cloudflared ollama \
  ai4artsed-gpu ai4artsed-production lab-frontend

# GPU
nvidia-smi

# Endpoints
curl http://localhost:17801/api/health
curl http://localhost:17803/api/health
curl http://localhost:5174/
ollama list

# Von aussen (PC1 oder Laptop)
curl https://lab2.ai4artsed.org/api/health
ssh -o ProxyCommand="cloudflared access ssh --hostname ssh-pc2.ai4artsed.org" ai4artsed@ssh-pc2.ai4artsed.org

# Reboot-Test
sudo reboot
# Nach ~2 Min alle Services erneut pruefen
```

## Monitoring (remote via SSH)

```bash
systemctl status ai4artsed-production ai4artsed-gpu ollama cloudflared nvidia-persistenced
nvidia-smi
journalctl -u ai4artsed-gpu -f
journalctl -u ai4artsed-production -f
```

---

## Troubleshooting

### GPU Service startet nicht
```bash
journalctl -u ai4artsed-gpu -e
# Haeufig: nvidia-persistenced nicht aktiv
systemctl status nvidia-persistenced
```

### Cloudflare Tunnel verbindet nicht
```bash
journalctl -u cloudflared -e
# Check: credentials-file Pfad korrekt? UUID stimmt?
ls ~/.cloudflared/*.json
```

### Ollama Modelle fehlen nach Kopie
```bash
# Ownership pruefen
ls -la /usr/share/ollama/.ollama/models/
sudo chown -R ollama:ollama /usr/share/ollama/.ollama/models/
sudo systemctl restart ollama
```

### pip install --no-index findet Packages nicht
```bash
# Wheel-Dateien muessen zur Python-Version passen (cp313 fuer Python 3.13)
ls /mnt/install-drive/pip-cache/*.whl | head -5
python3 --version
```
