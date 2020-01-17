#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

TOOLS=depot_tools
TOOLS_REPO=https://chromium.googlesource.com/chromium/tools/depot_tools.git
TOOLS_DIR=$DIR/$TOOLS

CHROMIUM=chromium
CHROMIUM_DIR=$DIR/$CHROMIUM
TARGET=out/Default

CERTS_PATH=$DIR/certs 

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

function write_leaf {
    if [[ -v SUDO_USER ]]; then
        sudo -u $SUDO_USER echo $@ >> leaf.cnf
    else
        echo $@ >> leaf.cnf
    fi
}

function build_leaf_certificates {
    rm leaf.cnf
    write_leaf 'SUBJECT_NAME = req_dn' 
    write_leaf 'KEY_SIZE = 2048' 

    write_leaf '[req]'
    write_leaf 'default_bits       = ${ENV::KEY_SIZE}' 
    write_leaf 'default_md         = sha256' 
    write_leaf 'string_mask        = utf8only' 
    write_leaf 'prompt             = no' 
    write_leaf 'encrypt_key        = no' 
    write_leaf 'distinguished_name = ${ENV::SUBJECT_NAME}' 
    write_leaf 'req_extensions     = req_extensions' 

    write_leaf '[req_dn]' 
    write_leaf 'C  = US' 
    write_leaf 'ST = California'
    write_leaf 'L  = Mountain View' 
    write_leaf 'O  = QUIC Server' 
    write_leaf 'CN = 127.0.0.1' 

    write_leaf '[req_extensions]' 
    write_leaf 'subjectAltName = @other_hosts' 

    write_leaf '[other_hosts]' 
    write_leaf "DNS.1 = $1" 
}

function generate_certs {

    log "Generating certs..."
    pushd $CERTS_PATH > /dev/null
    build_leaf_certificates $1
    run_cmd ./generate-certs.sh
    popd > /dev/null
    log "Certs generated."
}

function install_certs {
    log "Installing certs..."
    pushd $CERTS_PATH/out > /dev/null

    run_cmd certutil -d sql:$HOME/.pki/nssdb -D -n 'name'
    run_cmd certutil -d sql:$HOME/.pki/nssdb -A -n 'name' -i 2048-sha256-root.pem -t "C,,"
    run_cmd certutil -d sql:$HOME/.pki/nssdb -L

    popd > /dev/null
    log "Certs installed."
}
