# Sudo Command Execution for Claude Code Sessions

## Problem

Claude Code needs to execute sudo commands but cannot store passwords in scripts for security reasons.

## Solution

Use **stdin password passing** with heredoc:

```bash
cat << 'SUDOPW' | sudo -S command
YOUR_PASSWORD_HERE
SUDOPW
```

## Available Scripts

### 1. Update Cloudflared Config

**Script:** `update_cloudflared_config.sh`

**Usage:**
```bash
# From Claude Code session:
cat << 'SUDOPW' | ./scripts/update_cloudflared_config.sh /tmp/new_config.yml
YOUR_PASSWORD_HERE
SUDOPW
```

**What it does:**
1. Backs up current config to `/etc/cloudflared/config.yml.backup.TIMESTAMP`
2. Copies new config to `/etc/cloudflared/config.yml`
3. Restarts cloudflared service
4. Shows service status

## Security Notes

- ✅ Password passed via stdin (not visible in process list)
- ✅ No password stored in files
- ✅ Automatic backup before changes
- ✅ Service status verification after restart

## Manual Execution

If scripts fail, execute manually:

```bash
# 1. Backup current config
sudo cp /etc/cloudflared/config.yml /etc/cloudflared/config.yml.backup

# 2. Copy new config
sudo cp /tmp/new_config.yml /etc/cloudflared/config.yml

# 3. Restart service
sudo systemctl restart cloudflared

# 4. Check status
sudo systemctl status cloudflared
```

## For Future Sessions

When Claude Code needs sudo access:
1. User provides password as separate message
2. Claude uses heredoc pattern to execute commands
3. No password storage in any files
