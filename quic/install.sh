#!/bin/bash
LOG=installer
source ./env.sh

TMP=$DIR/tmp
TMP_CHROMIUM_DIR=$TMP/$CHROMIUM

function fetch_tools {
    # Fetch all necessary tools 
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
    # Fetch chromium source in a specific folder
    log "Fetching Chromium..."
   
    if [ -d $TMP_CHROMIUM_DIR ]; then
        log "Chromium already present in directory $TMP_CHROMIUM_DIR"
    else
        mkdir -p $TMP_CHROMIUM_DIR

        pushd $TMP_CHROMIUM_DIR > /dev/null
        run_cmd $TOOLS_DIR/fetch --nohooks --no-history $CHROMIUM
        run_cmd $TOOLS_DIR/gclient sync --nohooks --no-history
        popd > /dev/null

        log "Chromium fetched."
    fi
}

function copy_sources {
    log "Moving chromium source from temporary directory..."
    # Copy source from the temporary directory
    cp -r -n -v $TMP_CHROMIUM_DIR $DIR
    log "Chromium source moved"
}

function commandeer {
    log "Removing Google's source control from $CHROMIUM_DIR"
    rm -rf $CHROMIUM_DIR/.git
    rm -rf $CHROMIUM_DIR/src/.git
    log "Chromium ready."
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

function build_server {
    copy_sources
    build
    commandeer
}

function install_server {
    fetch_tools
    fetch_chromium

    copy_sources
    run_hooks
    build

    commandeer
}

function usage() {
    echo "Usage: $0 [OPTION]..."
    echo "Quic installer."

    echo -e "\nOptions: "
    printf "\t %- 30s %s\n" "-i | --install" "Install quic server."
    printf "\t %- 30s %s\n" "-b | --build" "Build quic server."
}


function parse_command_line_options() {
    while [ "${1:-}" != "" ]; do
        case $1 in
            -b | --build)
                FUNC=build_server
                ;;
            -i | --install)
                FUNC=install_server
                ;;
            * )
                usage
                exit 1
        esac

        shift
    done
}

FUNC=usage
parse_command_line_options "$@"
$FUNC
