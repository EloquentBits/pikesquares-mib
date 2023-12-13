#!/bin/sh
set -eu
APP_NAME="pikesquares"
DAEMON_ID="com.eloquentbits.${APP_NAME}"
SYSTEM_APP_DIR="/Library/Application Support/${APP_NAME}"
SYSTEM_DAEMON_PATH="/Library/LaunchDaemons/${DAEMON_ID}.plist"
USER_APP_DIR="${HOME}${SYSTEM_APP_DIR}"
USER_DAEMON_PATH="${HOME}${SYSTEM_DAEMON_PATH}"
DOMAIN="system"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_fail()
{
    echo "${RED}[x] $1${NC}"
}

log_success()
{
    echo "${GREEN}[+] $1${NC}"
}

test_certificates_installed()
{
    MKCERT_PATH="/usr/local/bin/mkcert"
    CAROOT="${USER_APP_DIR}/ssl"  # check the paths are the same in install/uninstall scripts
    WILDCARD_CERT="${CAROOT}/pikesquares.dev.pem"
    WILDCARD_CERT_KEY="${CAROOT}/pikesquares.dev-key.pem"
    if [[ -f $WILDCARD_CERT && -f $WILDCARD_CERT_KEY ]]; then
        log_success "Certificate and it private key successfully installed"
    else
        log_fail "Certificate and it private key NOT installed"
    fi
}

[ ! "$(sudo launchctl blame $DOMAIN/$DAEMON_ID &> /dev/null)" ] && log_success "Daemon not started automatically (user should start it itself)" || log_fail "Daemon WERE started automatically"
[ -f "/Library/LaunchDaemons/${DAEMON_ID}.plist" ] && log_success "Daemon successfully placed into system daemons folder" || log_fail "Daemon NOT placed in system daemons folder"
[ ! -z "$(sudo pkgutil --pkgs | grep $DAEMON_ID)" ] && log_success "Packages (binary, daemon) were written to packages database" || log_fail "Packages NOT written to db"
test_certificates_installed
[ -f "/usr/local/bin/pikesquares" ] && log_success "Binary successfully installed" || log_fail "Binary NOT installed"
[ -f "/usr/local/bin/pikesquares-uninstall" ] && log_success "Uninstaller successfully created" || log_fail "Uninstaller NOT created"
