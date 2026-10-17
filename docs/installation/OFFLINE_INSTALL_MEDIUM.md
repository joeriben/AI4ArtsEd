# 4TB Offline-Installationsmedium erstellen (auf PC1)

> ⚠️ **DEPRECATED** (as of 2026-05-17)
>
> Dieses Dokument beschreibt einen Offline-Install-Workflow über externe HD inklusive
> Ollama-Modellen und der älteren Verzeichnisarchitektur. Aktuelle Migrationen
> erfolgen per rsync übers LAN; Ollama existiert nicht mehr (ersetzt durch in-process
> `llama-cpp-python`).
>
> **Für Neu-Installationen** [`UBUNTU_SERVER_FRESH_INSTALL.md`](UBUNTU_SERVER_FRESH_INSTALL.md) **verwenden** (Phase 4 dort beschreibt den rsync-Pfad).
>
> Der Inhalt unten bleibt nur als historischer Kontext erhalten.

---

Anleitung zum Erstellen einer externen HD, die alles enthaelt um PC2 ohne Internet-Downloads einzurichten.

**Erstellt:** 2026-02-23
**Geschaetzte Groesse:** ~950 GB (von 4 TB)

---

## Verzeichnisstruktur

```
/mnt/install-drive/
  README.md                          <- Anleitung fuer Claude auf PC2
  install.sh                         <- Master-Installationsscript

  installers/
    ollama-install.sh                <- curl -fsSL https://ollama.com/install.sh
    cloudflared-linux-amd64.rpm      <- dnf download oder von CF-Website
    node-v22.22.0-linux-x64.tar.xz  <- nodejs.org Binary-Tarball

  system-deps/
    *.rpm                            <- dnf download fuer WeasyPrint-Deps etc.

  pip-cache/
    *.whl                            <- pip download -d ./pip-cache -r requirements.txt
    torch-nightly/                   <- pip download --pre torch torchaudio torchvision
    spacy-models/
      de_core_news_lg-*.whl
      xx_ent_wiki_sm-*.whl

  npm-cache/
    node_modules/                    <- Kopie von node_modules (pragmatischste Loesung)

  repos/
    ai4artsed.git/                   <- git clone --bare (kompakt, alle Branches)
    heartlib/                        <- Vollstaendige Kopie inkl. ckpt/ (~28GB)
    ImageBind/                       <- git clone (~6MB)
    MMAudio/                         <- git clone (~25MB)

  models/
    ollama/                          <- Ollama Modell-Blobs (/usr/share/ollama/.ollama/)
      manifests/
      blobs/
    huggingface/                     <- ~/.cache/huggingface/hub/ (selektiv)
    diffusers-extra/                 <- ~/ai/models/diffusers/
    diffusers-cache-extra/           <- ~/ai/diffusers_cache/
    swarmui/                         <- SwarmUI Models/ (komplett)
    gpu-service-weights/             <- gpu_service/weights/ + ext_weights/

  configs/
    systemd/                         <- Alle .service und .conf Dateien
    ssh/                             <- 99-hardening.conf

  scripts/
    setup_cloudflared_pc2.sh
    6_start_cloudflared_lab_pc2.sh
    6_start_cloudflared_both_pc2.sh
    6_stop_cloudflared_pc2.sh
```

---

## Schritt 1: Verzeichnisstruktur anlegen

```bash
DRIVE="/mnt/install-drive"
mkdir -p $DRIVE/{installers,system-deps,pip-cache/torch-nightly,pip-cache/spacy-models}
mkdir -p $DRIVE/{npm-cache,repos,models,configs/systemd,configs/ssh,scripts}
mkdir -p $DRIVE/models/{ollama,huggingface,swarmui,gpu-service-weights}
```

## Schritt 2: Installers herunterladen

```bash
# Ollama Installer
curl -fsSL https://ollama.com/install.sh -o $DRIVE/installers/ollama-install.sh

# Cloudflared RPM
sudo dnf download --destdir=$DRIVE/installers/ cloudflared 2>/dev/null || \
  curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-x86_64.rpm \
    -o $DRIVE/installers/cloudflared-linux-amd64.rpm

# Node.js Binary
curl -L https://nodejs.org/dist/v22.22.0/node-v22.22.0-linux-x64.tar.xz \
  -o $DRIVE/installers/node-v22.22.0-linux-x64.tar.xz
```

## Schritt 3: System-Dependencies (Fedora RPMs)

```bash
sudo dnf download --resolve --destdir=$DRIVE/system-deps/ \
  cairo-devel pango-devel libjpeg-turbo-devel giflib-devel gobject-introspection-devel \
  gcc gcc-c++ python3-devel git make
```

## Schritt 4: Python Packages (Wheels)

```bash
VENV="<repo>/venv/bin"

# Haupt-Requirements (ohne PyTorch)
$VENV/pip download -d $DRIVE/pip-cache/ -r requirements.txt

# PyTorch Nightly fuer Blackwell (CUDA 13.0)
$VENV/pip download -d $DRIVE/pip-cache/torch-nightly/ \
  --pre torch torchaudio torchvision \
  --index-url https://download.pytorch.org/whl/nightly/cu130

# SpaCy-Modelle
$VENV/pip download -d $DRIVE/pip-cache/spacy-models/ \
  https://github.com/explosion/spacy-models/releases/download/de_core_news_lg-3.8.0/de_core_news_lg-3.8.0-py3-none-any.whl \
  https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.8.0/xx_ent_wiki_sm-3.8.0-py3-none-any.whl

# heartlib Dependencies
$VENV/pip download -d $DRIVE/pip-cache/ \
  vector-quantize-pytorch soundfile bitsandbytes einops modelscope torchtune torchao librosa
```

## Schritt 5: NPM Packages

```bash
# node_modules direkt kopieren (npm-caching ist fragil)
rsync -av <repo>/public/ai4artsed-frontend/node_modules/ \
  $DRIVE/npm-cache/node_modules/
```

## Schritt 6: Git Repos

```bash
# Bare Clone (kompakt, alle Branches)
git clone --bare <repo>/.git $DRIVE/repos/ai4artsed.git

# heartlib komplett (inkl. Checkpoints ~28GB)
rsync -av --progress <AI_TOOLS_BASE>/heartlib/ $DRIVE/repos/heartlib/

# ImageBind + MMAudio (klein, Code only)
cp -r <AI_TOOLS_BASE>/ImageBind/ $DRIVE/repos/ImageBind/
cp -r <AI_TOOLS_BASE>/MMAudio/ $DRIVE/repos/MMAudio/
```

## Schritt 7: AI Modelle

### Ollama (nur benoetigte 5, ~16GB)

**Voraussetzung:** `ollama pull qwen3:4b` muss vorher ausgefuehrt werden (fehlt auf PC1).

| Modell | Zweck | Groesse |
|--------|-------|---------|
| `llama-guard3:1b` | SAFETY_MODEL | ~1.6 GB |
| `qwen3:1.7b` | DSGVO_VERIFY_MODEL | ~1.4 GB |
| `qwen3-vl:2b` | VLM_SAFETY_MODEL | ~1.9 GB |
| `qwen3:4b` | LOCAL_DEFAULT_MODEL | ~3 GB |
| `llama3.2-vision:latest` | LOCAL_VISION_MODEL | ~7.8 GB |

```bash
sudo rsync -av --progress /usr/share/ollama/.ollama/models/ $DRIVE/models/ollama/
```

### HuggingFace Cache (selektiv, ~129GB)

HuggingFace Cache ist direkt portabel. Verzeichnisstruktur kopieren, auf PC2 unter
`~/.cache/huggingface/hub/` platzieren — `from_pretrained()` findet alles automatisch.

```bash
for model in \
  "models--stabilityai--stable-diffusion-3.5-large" \
  "models--stabilityai--stable-diffusion-3.5-large-turbo" \
  "models--stabilityai--stable-diffusion-xl-base-1.0" \
  "models--Wan-AI--Wan2.2-TI2V-5B-Diffusers" \
  "models--openai--clip-vit-large-patch14" \
  "models--apple--DFN5B-CLIP-ViT-H-14-384" \
  "models--nvidia--bigvgan_v2_44khz_128band_512x"; do
  rsync -av --progress ~/.cache/huggingface/hub/$model $DRIVE/models/huggingface/
done

# Extra Diffusers Caches
rsync -av --progress ~/ai/models/diffusers/ $DRIVE/models/diffusers-extra/
rsync -av --progress ~/ai/diffusers_cache/ $DRIVE/models/diffusers-cache-extra/
```

### SwarmUI/ComfyUI (komplett, ~450GB)

```bash
rsync -av --progress ~/ai/SwarmUI/Models/ $DRIVE/models/swarmui/ \
  --exclude='.cache'
```

### GPU Service Weights (~6GB)

```bash
rsync -av --progress ~/ai/ai4artsed_development/gpu_service/weights/ \
  $DRIVE/models/gpu-service-weights/weights/
rsync -av --progress ~/ai/ai4artsed_development/gpu_service/ext_weights/ \
  $DRIVE/models/gpu-service-weights/ext_weights/
```

## Schritt 8: Konfigurationsdateien

```bash
# Cloudflare Scripts
cp ~/setup_cloudflared_pc2.sh $DRIVE/scripts/
cp ~/6_start_cloudflared_*_pc2.sh $DRIVE/scripts/
cp ~/6_stop_cloudflared_pc2.sh $DRIVE/scripts/

# SSH Hardening
cat > $DRIVE/configs/ssh/99-hardening.conf << 'EOF'
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
AllowUsers ai4artsed
ClientAliveInterval 30
ClientAliveCountMax 6
EOF
```

## Schritt 9: README fuer PC2

Die Datei `$DRIVE/README.md` sollte auf `docs/installation/PC2_INSTALLATION.md` verweisen — diese enthaelt die vollstaendige Installationsanleitung fuer Claude Code auf PC2.

---

## Groessenabschaetzung

| Kategorie | Groesse |
|-----------|---------|
| Installers + RPMs | ~1 GB |
| pip wheels + torch nightly | ~15 GB |
| Git Repos + heartlib | ~30 GB |
| Ollama Modelle (5 Stueck) | ~16 GB |
| HuggingFace Modelle | ~129 GB |
| SwarmUI Modelle | ~450 GB |
| GPU Service Weights | ~6 GB |
| npm / Frontend | ~1 GB |
| **Gesamt** | **~650 GB von 4 TB** |
