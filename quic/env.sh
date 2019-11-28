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
