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

function generate_certs {
    log "Generating certs..."
    pushd $CERTS_PATH > /dev/null
    ./generate-certs.sh
    popd > /dev/null
    log "Certs generated."
}

fetch_tools
fetch_chromium
run_hooks
build
generate_certs
