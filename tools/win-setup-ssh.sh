#!/usr/bin/env bash
# Install OpenSSH Server in win10 (via QEMU guest agent) and authorize a project key.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY="$ROOT/tools/win10_agent_ed25519"
PUB="$KEY.pub"
PY="$ROOT/tools/win_guest.py"
HOST_ALIAS_IP="${WIN10_IP:-192.168.122.89}"

if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -N "" -f "$KEY" -C "flydigi-win10-agent"
  echo "Created $KEY"
fi
PUBTEXT="$(tr -d '\n' <"$PUB")"

echo "Installing OpenSSH.Server (may take a few minutes)…"
python3 "$PY" --timeout 600 --ps "
\$ProgressPreference = 'SilentlyContinue'
\$cap = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if (\$cap.State -ne 'Installed') {
  Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-String
}
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic
New-Item -Force -ItemType Directory -Path \$env:ProgramData\ssh | Out-Null
# SYSTEM / admin login uses administrators_authorized_keys
\$ak = Join-Path \$env:ProgramData 'ssh\administrators_authorized_keys'
Set-Content -Path \$ak -Value '$PUBTEXT' -Encoding ascii
icacls \$ak /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F' | Out-Null
Get-Service sshd | Format-List Name,Status,StartType | Out-String
"

# SSH config snippet for the user
CFG_SNIP="# Flydigi Space Station Windows oracle
Host win10
	HostName $HOST_ALIAS_IP
	User jochem
	IdentityFile $KEY
	IdentitiesOnly yes
	StrictHostKeyChecking accept-new
"

echo
echo "Add this to ~/.ssh/config if missing:"
echo "$CFG_SNIP"
if ! grep -q '^Host win10$' "$HOME/.ssh/config" 2>/dev/null; then
  printf '\n%s\n' "$CFG_SNIP" >>"$HOME/.ssh/config"
  echo "Appended Host win10 to ~/.ssh/config"
fi

echo "Testing ssh…"
sleep 2
ssh -o BatchMode=yes -o ConnectTimeout=5 win10 "whoami" || {
  echo "SSH still blocked — check Windows Firewall / that OpenSSH finished installing."
  echo "Guest agent still works: python3 tools/win_guest.py whoami"
  exit 1
}
echo "SSH OK"
