#!/bin/bash
LOG=runner
BASEDIR=$(dirname "$0")
source $BASEDIR/env.sh

OUT_DIR=$CHROMIUM_DIR/src/$TARGET

HOST=127.0.0.1
PORT=6121
METRICS_PORT=""
PROFILE="profile"
SITE=www.example.org

TC=/sbin/tc
RESET=""
BURST="20000"
CERTS=""
HEADLESS=""
VIDEO="bojack"
DASH_ARGS=""
DASH_COMPRESS=""
VERBOSE=""
CC="bbr"
ABR="bb"

function build {
    log "Building $1"
    run_cmd $TOOLS_DIR/ninja -C $OUT_DIR $1
}

function setup_certs {
    if [ -z "$CERTS" ] ; then 
        log "Skipping certs setup."    
    else
        log "Setup certs..."
        generate_certs $SITE
        install_certs
        log "Certs setup."
    fi
}

function set_network_conditions {
    if [ ! -z "$RESET" ] ; then
        log "Resetting qdiscs..."
        priv_run_cmd $TC qdisc del dev lo root
    fi
}

function build_dash_client_npm {
    log "Building dash client..."
    pushd $DIR/../dash > /dev/null

    SRC=$DIR/../dash
    DST=$DIR/sites/$SITE

    # copy config to dash
    run_cmd rm $SRC/dist/video.json
    run_cmd cp $DIR/sites/$VIDEO/config.json $SRC/dist/video.json 

    if [ ! -z $METRICS_PORT ]; then 
        DASH_ARGS="${DASH_ARGS} record metrics-port=${METRICS_PORT}"
    fi
    if [ ! -z $PORT ]; then 
        DASH_ARGS="${DASH_ARGS} quic-port=${PORT}"
    fi
    run_cmd npm run build $DASH_ARGS $SITE
    if [ ! -z $DASH_COMPRESS ]; then 
        run_cmd npm run build:compress
        run_cmd ls -lh dist
    fi

    run_cmd run_cmd rm -rf $DST
    run_cmd mkdir -p $DST
    run_cmd cp -r $SRC/dist $DST
    run_cmd cp $SRC/index.html $DST

    run_cmd rm $SRC/manifest.mpd
    run_cmd cp $DIR/sites/$VIDEO/manifest.mpd $SRC
    run_cmd cp $DIR/sites/$VIDEO/manifest.mpd $DST
    
    popd > /dev/null
    log "Dash client built."
}

function quic_server {
    build_dash_client_npm
    build dash_server

    setup_certs
    set_network_conditions

    run_cmd $OUT_DIR/dash_server \
        $VERBOSE \
        --quic_config_path=$DIR/sites/$VIDEO/config.json \
        --cc_type=$CC \
        --abr_type=$ABR \
        --port=$PORT \
        --site=$SITE \
        --certificate_file=$CERTS_PATH/out/leaf_cert.pem \
        --key_file=$CERTS_PATH/out/leaf_cert.pkcs8 
}

function quic_chrome {
    RED_PORT=443
    if [[ -v SUDO_USER ]]; then
        sudo -u $SUDO_USER google-chrome-stable \
            --v=1 \
            $HEADLESS \
            --user-data-dir=/tmp/$PROFILE \
            --no-proxy-server \
            --enable-quic \
            --origin-to-force-quic-on=$SITE:$PORT \
            --autoplay-policy=no-user-gesture-required \
            --ignore-certificate-errors \
            --allow-running-insecure-content \
            --enable-features=NetworkService \
            --incognito \
            --host-resolver-rules="MAP * 127.0.0.1" \
            https://$SITE:$PORT
    else
        google-chrome-stable \
            --v=1 \
            $HEADLESS \
            --user-data-dir=/tmp/$PROFILE \
            --no-proxy-server \
            --enable-quic \
            --origin-to-force-quic-on=$SITE:$PORT \
            --autoplay-policy=no-user-gesture-required \
            --ignore-certificate-errors \
            --allow-running-insecure-content \
            --enable-features=NetworkService \
            --incognito \
            --host-resolver-rules="MAP * 127.0.0.1" \
            https://$SITE:$PORT
    fi
}

function usage() {
    if [ ! -z "$CERTS" ] ; then 
        setup_certs
        exit 0;
    fi
    echo "Usage: $0 [OPTION]..."
    echo "Quic runner."

    echo -e "\nOptions: "
    printf "\t %- 30s %s\n" "-s | --server" "Run a quic server."
    printf "\t %- 30s %s\n" "-b | --build" "Build quic client and server."
    printf "\t %- 30s %s\n" "-vid | --video" "Specify name of video to be served."
    printf "\t %- 30s %s\n" "--chrome" "Run a quic client in Chrome."
    printf "\t %- 30s %s\n" "--cc [congestion-control]" "Select congestion control from [bbr, abbr, xbbr, pcc, cubic, reno, target, gap]."
    printf "\t %- 30s %s\n" "--abr [server-abr-type]" "Select server-side abor from [bb, random, worthed, target, target2, target3, gap, remote]."
    printf "\t %- 30s %s\n" "--port [int]" "Change the port. (default 6121)"
    printf "\t %- 30s %s\n" "--profile [str]" "Change the chrome profile name to run."
    printf "\t %- 30s %s\n" "(-mp | --metrics-port) [int]" "Change the to which chrome talks to. (default 8080)"
    printf "\t %- 30s %s\n" "--site [url]" "Change the site serverd. (default www.example.org)"
    printf "\t %- 30s %s\n" "--certs" "Regenerate and install server certificates."
    printf "\t %- 30s %s\n" "-d | --dash" "Pass a command line argument to dash."
    printf "\t %- 30s %s\n" "--headless" "Activate headless mode for Chrome."
    printf "\t %- 30s %s\n" "-dc | --dash-compress" "Compress the dash js bundle."
    
    echo -e "\nExamples: "
    printf "\t %- 30s %s\n" "sudo run.sh --bw 2 --latency 100 -s --site www.example.org"
    printf "\t %- 30s %s\n" "run.sh -s"
    printf "\t %- 30s %s\n" "run.sh -c --port 6333 --site www.example.org"
}


function parse_command_line_options() {
    while [ "${1:-}" != "" ]; do
        case $1 in
            -b | --build)
                build net
                build dash_server
                exit 0
                ;;
            -vid | --video) 
                shift
                VIDEO=$1
                ;;
            -s | --server)
                FUNC=quic_server
                ;;
            --chrome)
                FUNC=quic_chrome
                ;;
            --cc)
                shift
                if [ $1 == "bbr" ]; then
                    CC=$1
                elif [ $1 == "bbr2" ]; then
                    CC=$1
                elif [ $1 == "abbr" ]; then # Custom #1
                    CC=$1
                elif [ $1 == "xbbr" ]; then # Custom #1 -- no adaptation
                    CC=$1
                elif [ $1 == "pcc" ]; then
                    CC=$1
                elif [ $1 == "cubic" ]; then
                    CC=$1
                elif [ $1 == "reno" ]; then 
                    CC=$1
                elif [ $1 == "target" ]; then 
                    CC=$1
                elif [ $1 == "gap" ]; then 
                    CC=$1
                elif [ $1 == "minerva" ]; then 
                    CC=$1
                else
                    echo "Congestion control $1 not recognized."
                fi
                ;;
            --abr)
                shift
                if [ $1 == "bb" ]; then
                    ABR=$1
                elif [ $1 == "random" ]; then
                    ABR=$1
                elif [ $1 == "worthed" ]; then
                    ABR=$1
                elif [ $1 == "target" ]; then 
                    ABR=$1
                elif [ $1 == "target2" ]; then 
                    ABR=$1
                elif [ $1 == "target3" ]; then 
                    ABR=$1
                elif [ $1 == "gap" ]; then 
                    ABR=$1
                elif [ $1 == "remote" ]; then 
                    ABR=$1
                elif [ $1 == "minerva" ]; then 
                    ABR=$1
                else
                    echo "Abr $1 not recognized."
                fi
                ;;
            --host)
                shift
                HOST=$1
                ;;
            --port)
                shift
                PORT=$1
                ;;
            -mp | --metrics-port)
                shift
                METRICS_PORT=$1
                ;;
            --site)
                shift
                SITE=$1
                ;;
            --reset)
                RESET="yes"
                ;;
            --headless)
                HEADLESS="--headless --disable-gpu --remote-debugging-port=9222"
                ;;
            --profile)
                shift
                PROFILE=$1
                ;;
            --certs)
                CERTS="yes"
                ;;
            -d | --dash)
                shift
                DASH_ARGS="${DASH_ARGS} $1"
                ;;
            -dc | --dash-compress)
                DASH_COMPRESS="yes"
                ;;
            -v | --verbose)
                VERBOSE="--v=1"
                ;;
            -h | --help )
                usage
                exit 0
                ;;
            * )
                CERTS=""
                usage
                exit 1
        esac

        shift
    done
}

FUNC=usage
parse_command_line_options "$@"
$FUNC
