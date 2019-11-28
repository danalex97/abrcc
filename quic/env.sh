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
    $@
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
    run_cmd $TOOLS_DIR/autoninja -C $TARGET chrome

    popd > /dev/null
    log "Build finished."
}
