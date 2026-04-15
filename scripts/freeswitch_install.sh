#!/bin/bash
set -e

echo "===================================================="
echo " FreeSWITCH Source Installation (MySQL + ODBC + Lua)"
echo " Ubuntu 22.04 LTS"
echo "===================================================="

FS_VERSION="v1.10.12"
SRC_DIR="/usr/src"
PREFIX="/usr/local/freeswitch"

export DEBIAN_FRONTEND=noninteractive

# ----------------------------------------------------
# 1. Install build dependencies (NO PostgreSQL)
# ----------------------------------------------------
echo "[1/9] Installing build dependencies..."

apt update
apt install -y \
  git wget curl \
  build-essential pkg-config \
  autoconf automake libtool cmake \
  libssl-dev zlib1g-dev libdb-dev \
  libncurses5-dev libexpat1-dev \
  libgdbm-dev bison flex \
  libsqlite3-dev \
  libcurl4-openssl-dev libpcre3-dev \
  libspeex-dev libspeexdsp-dev \
  libsndfile1-dev libtiff-dev \
  libldns-dev libedit-dev \
  liblua5.2-dev python3-dev \
  uuid-dev yasm \
  libmysqlclient-dev \
  unixodbc unixodbc-dev odbc-mariadb \
  plocate sngrep
apt install -y \
  libtool \
  libtool-bin \
  automake \
  autoconf \
  autoconf-archive \
  pkg-config \
  m4
# ----------------------------------------------------
# 2. Build libks
# ----------------------------------------------------
echo "[2/9] Building libks..."
cd $SRC_DIR
rm -rf libks
git clone https://github.com/signalwire/libks.git
cd libks
cmake . -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
make install
ldconfig

# ----------------------------------------------------
# 3. Build sofia-sip
# ----------------------------------------------------
echo "[3/9] Building sofia-sip..."
cd "$SRC_DIR"
rm -rf sofia-sip
git clone https://github.com/freeswitch/sofia-sip.git
cd sofia-sip

# --- Workaround for newer automake: install.sh -> install-sh / BUG.am issue ---
# Provide install-sh expected by automake
cp -f /usr/share/automake-*/install-sh . 2>/dev/null || cp -f /usr/share/automake/install-sh .
chmod +x install-sh

# Create harmless BUG.am to avoid automake "install.sh anachronism" failure
cat > BUG.am <<'EOF'
# workaround file for newer automake
EOF
# ---------------------------------------------------------------------------

libtoolize --force --copy --install
autoreconf -fiv

./configure --prefix=/usr/local
make -j"$(nproc)"
make install
ldconfig

# sanity check (optional but recommended)
pkg-config --modversion sofia-sip-ua

# ----------------------------------------------------
# 4. Build spandsp
# ----------------------------------------------------
cd $SRC_DIR
rm -rf spandsp
git clone https://github.com/freeswitch/spandsp.git
cd spandsp

./bootstrap.sh
./configure
make -j$(nproc)
make install
ldconfig
pkg-config --modversion spandsp

# 5. Build signalwire-c
# ----------------------------------------------------
echo "[5/9] Building signalwire-c..."
cd $SRC_DIR
rm -rf signalwire-c
git clone https://github.com/signalwire/signalwire-c.git
cd signalwire-c
cmake .
make -j$(nproc)
make install
ldconfig

# ----------------------------------------------------
# 6. Clone & bootstrap FreeSWITCH
# ----------------------------------------------------
echo "[6/9] Cloning FreeSWITCH..."
cd $SRC_DIR
rm -rf freeswitch
git clone https://github.com/signalwire/freeswitch.git
cd freeswitch
git checkout $FS_VERSION
./bootstrap.sh -j

# ----------------------------------------------------
# 7. Configure FreeSWITCH modules
# ----------------------------------------------------
echo "[7/9] Configuring FreeSWITCH modules..."
cp -f build/modules.conf.in modules.conf

cd build
sed -i 's|#applications/mod_curl|applications/mod_curl|' modules.conf.in
sed -i 's|#applications/mod_json_cdr|applications/mod_json_cdr|' modules.conf.in
sed -i 's|#xml_int/mod_xml_cdr|xml_int/mod_xml_cdr|' modules.conf.in
sed -i 's|#xml_int/mod_xml_curl|xml_int/mod_xml_curl|' modules.conf.in
sed -i 's|#applications/mod_nibblebill|applications/mod_nibblebill|' modules.conf.in
sed -i 's|#applications/mod_db|applications/mod_db|' modules.conf.in
sed -i 's|#databases/mod_odbc|databases/mod_odbc|' modules.conf.in
sed -i 's|#event_handlers/mod_json_cdr|event_handlers/mod_json_cdr|' modules.conf.in
sed -i 's|#applications/mod_callcenter|applications/mod_callcenter|' modules.conf.in
sed -i 's|#applications/mod_spy|applications/mod_spy|' modules.conf.in
sed -i 's|^applications/mod_av|#applications/mod_av|' modules.conf.in
sed -i 's|^databases/mod_pgsql|#databases/mod_pgsql|' modules.conf.in
sed -i 's|^[[:space:]]*applications/mod_spandsp|#applications/mod_spandsp|' modules.conf.in
cd ..
sed -i 's|#applications/mod_curl|applications/mod_curl|' modules.conf
sed -i 's|#applications/mod_json_cdr|applications/mod_json_cdr|' modules.conf
sed -i 's|#xml_int/mod_xml_cdr|xml_int/mod_xml_cdr|' modules.conf
sed -i 's|#xml_int/mod_xml_curl|xml_int/mod_xml_curl|' modules.conf
sed -i 's|#applications/mod_nibblebill|applications/mod_nibblebill|' modules.conf
sed -i 's|#applications/mod_db|applications/mod_db|' modules.conf
sed -i 's|#databases/mod_odbc|databases/mod_odbc|' modules.conf
sed -i 's|#event_handlers/mod_json_cdr|event_handlers/mod_json_cdr|' modules.conf
sed -i 's|#applications/mod_callcenter|applications/mod_callcenter|' modules.conf
sed -i 's|#applications/mod_spy|applications/mod_spy|' modules.conf
sed -i 's|^applications/mod_av|#applications/mod_av|' modules.conf
sed -i 's|^databases/mod_pgsql|#databases/mod_pgsql|' modules.conf
sed -i 's|^[[:space:]]*applications/mod_spandsp|#applications/mod_spandsp|' modules.conf

set -e  # stop on error

PREFIX="/usr/local/freeswitch"

# ----------------------------------------------------
# 8. Configure, build & install FreeSWITCH
# ----------------------------------------------------
echo "[8/9] Building FreeSWITCH..."

./configure --prefix=$PREFIX \
  --enable-core-mysql-support \
  --disable-libvpx \
  --enable-zrtp \
  --disable-av

make -j$(nproc)
make install
make sounds-install moh-install

# ----------------------------------------------------
# Setup systemd service
# ----------------------------------------------------
echo "▶ Setting up systemd service..."

cat >/etc/systemd/system/freeswitch.service <<EOF
[Unit]
Description=FreeSWITCH
After=network.target

[Service]
Type=forking
ExecStart=$PREFIX/bin/freeswitch -ncwait -nonat
ExecStop=$PREFIX/bin/fs_cli -x "shutdown"
Restart=always
RestartSec=3
LimitNOFILE=100000

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable freeswitch
systemctl start freeswitch

# Wait for FS to be ready
sleep 5

# ----------------------------------------------------
# Detect FreeSWITCH user
# ----------------------------------------------------
echo "▶ Detecting FreeSWITCH user..."

FS_USER=$(ps aux | grep '[f]reeswitch' | awk '{print $1}' | head -n 1)

if [ -z "$FS_USER" ]; then
    if id "freeswitch" &>/dev/null; then
        FS_USER="freeswitch"
    else
        FS_USER=$(whoami)
    fi
fi

FS_GROUP=$(id -gn $FS_USER)

echo "Using User: $FS_USER"
echo "Using Group: $FS_GROUP"

# ----------------------------------------------------
# Paths
# ----------------------------------------------------
FS_CONF="$PREFIX/etc/freeswitch"
FS_SIP_PROFILE_DIR="$FS_CONF/sip_profiles"
FS_DIALPLAN="$FS_CONF/dialplan"

FREESWITCH_DIR="/root/ai-voice-agent/freeswitch"
SIP_PROFILE_DIR="$FREESWITCH_DIR/sip_profiles"
SCRIPT_DIR="$FREESWITCH_DIR/scripts"
DIALPLAN_DIR="$FREESWITCH_DIR/dialplan"

FS_BIN="$PREFIX/bin"

# ----------------------------------------------------
# Ensure PATH
# ----------------------------------------------------
echo "▶ Configuring FreeSWITCH CLI..."

if ! command -v fs_cli >/dev/null 2>&1; then
    echo "export PATH=\$PATH:$FS_BIN" > /etc/profile.d/freeswitch.sh
    chmod +x /etc/profile.d/freeswitch.sh
    export PATH=$PATH:$FS_BIN
fi

# Avoid duplicate entry in bashrc
grep -qxF "export PATH=\$PATH:$FS_BIN" ~/.bashrc || \
echo "export PATH=\$PATH:$FS_BIN" >> ~/.bashrc

# ----------------------------------------------------
# Validate directories
# ----------------------------------------------------
[ -d "$SIP_PROFILE_DIR" ] || { echo "❌ Missing SIP profiles"; exit 1; }
[ -d "$DIALPLAN_DIR" ] || { echo "❌ Missing Dialplan"; exit 1; }
[ -d "$SCRIPT_DIR" ] || { echo "❌ Missing Scripts"; exit 1; }

# ----------------------------------------------------
# Deploy SIP Profiles
# ----------------------------------------------------
echo "▶ Deploying SIP Profiles..."
[ -d "$FS_SIP_PROFILE_DIR" ] && rm -rf ${FS_SIP_PROFILE_DIR:?}/*
cp -r ${SIP_PROFILE_DIR}/. ${FS_SIP_PROFILE_DIR}/
chown -R ${FS_USER}:${FS_GROUP} ${FS_SIP_PROFILE_DIR}

# ----------------------------------------------------
# Deploy Dialplan
# ----------------------------------------------------
echo "▶ Deploying Dialplan..."
[ -d "$FS_DIALPLAN" ] && rm -rf ${FS_DIALPLAN:?}/*
cp -r ${DIALPLAN_DIR}/. ${FS_DIALPLAN}/
chown -R ${FS_USER}:${FS_GROUP} ${FS_DIALPLAN}

# ----------------------------------------------------
# Deploy Scripts
# ----------------------------------------------------
echo "▶ Deploying Scripts..."
cp -r ${SCRIPT_DIR}/. $PREFIX/share/freeswitch/scripts/
chown -R ${FS_USER}:${FS_GROUP} $PREFIX/share/freeswitch/scripts/

# ----------------------------------------------------
# Create symlink for fs_cli in /usr/local/bin
# ----------------------------------------------------
ln -sf $PREFIX/bin/freeswitch /usr/local/bin/freeswitch
ln -sf $PREFIX/bin/fs_cli /usr/local/bin/fs_cli

# ----------------------------------------------------
# Reload FreeSWITCH
# ----------------------------------------------------
echo "▶ Reloading FreeSWITCH..."
$PREFIX/bin/fs_cli -x "reloadxml"

# ----------------------------------------------------
# 9. Finalization
# ----------------------------------------------------
echo "[9/9] Finalizing installation..."

systemctl restart freeswitch
systemctl status freeswitch --no-pager

echo "===================================================="
echo " ✅ FreeSWITCH Installed & Configured Successfully!"
echo " Binary : $PREFIX/bin/freeswitch"
echo " CLI    : $PREFIX/bin/fs_cli"
echo "===================================================="
