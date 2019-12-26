#!/bin/bash
LOG=installer
source ./env.sh

function fetch_tools {
    log "Fetching tools..."
    
    if [ -d $TOOLS_DIR ]; then
        log "$TOOLS_DIR already present..."
    else
        run_cmd git clone $TOOLS_REPO
    fi
    log "Tools dir: $TOOLS_DIR"
    log "Tools fetched."
}

function fetch_chromium {
    log "Fetching Chromium..."
    
    mkdir -p $CHROMIUM_DIR

    pushd $CHROMIUM_DIR > /dev/null
    run_cmd $TOOLS_DIR/fetch --nohooks --no-history $CHROMIUM
    run_cmd $TOOLS_DIR/gclient sync --nohooks --no-history
    popd > /dev/null

    log "Chromium fetched."
}

function run_hooks {
    log "Running hooks..."
    pushd $DIR/$CHROMIUM/src > /dev/null

    log "Install deps..."
    run_cmd ./build/install-build-deps.sh

    log "Run hooks..."
    run_cmd $TOOLS_DIR/gclient runhooks

    popd > /dev/null
    log "Hooks ran."
}

function build {
    build_chromium
}

fetch_tools
fetch_chromium
run_hooks
build
generate_certs
install_certs
