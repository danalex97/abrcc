#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

TOOLS=depot_tools
TOOLS_REPO=https://chromium.googlesource.com/chromium/tools/depot_tools.git
TOOLS_DIR=$DIR/$TOOLS

CHROMIUM=chromium
CHROMIUM_DIR=$DIR/$CHROMIUM
TARGET=out/Default

CERTS_PATH=$CHROMIUM_DIR/src/net/tools/quic/certs 

function log {
    echo "[$LOG] $@"
}

function run_cmd {
    echo "[running] $@"
    if [[ -v SUDO_USER ]]; then
        sudo -u $SUDO_USER $@
    else
        $@
    fi
}

function priv_run_cmd {
    echo "[sudo running] $@"
    if [[ -v SUDO_USER ]]; then
        $@
    else 
        echo "[sudo needed] $@"
        echo "Stopping script"
        exit 1
    fi
}

function build_chromium {
    log "Build..."
    pushd $DIR/$CHROMIUM/src > /dev/null

    log "Setup build..."
    run_cmd $TOOLS_DIR/gn gen $TARGET

    log "Chainging PATH variable..."
    export PATH="$PATH:$TOOLS_DIR"
    echo $PATH
 
    log "Build Chromium..."
    run_cmd $TOOLS_DIR/autoninja -C $TARGET quic_server
    run_cmd $TOOLS_DIR/autoninja -C $TARGET net

    popd > /dev/null
    log "Build finished."
}

function generate_certs {
    log "Generating certs..."
    pushd $CERTS_PATH > /dev/null
    run_cmd ./generate-certs.sh
    popd > /dev/null
    log "Certs generated."
}

function install_certs {
    log "Installing certs..."
    pushd $CERTS_PATH/out > /dev/null

    run_cmd certutil -d sql:$HOME/.pki/nssdb -D -n cert
    run_cmd certutil -d sql:$HOME/.pki/nssdb -A -n cert -i 2048-sha256-root.pem -t "C,,"
    
    run_cmd certutil -d sql:$HOME/.pki/nssdb -L

    popd > /dev/null
    log "Certs installed."
}
