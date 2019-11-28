#!/bin/bash
LOG=runner
source ./env.sh

OUT_DIR=$CHROMIUM_DIR/src/$TARGET

HOST=127.0.0.1
PORT=6121
SITE=www.example.org

function build {
    log "Building $1"
    run_cmd $TOOLS_DIR/ninja -C $OUT_DIR $1
}

function quic_server {
    build quic_server
    run_cmd $OUT_DIR/quic_server \
        --v=1 \
        --quic_response_cache_dir=$DIR/sites/$SITE \
        --port=$PORT \
        --certificate_file=$CERTS_PATH/out/leaf_cert.pem \
        --key_file=$CERTS_PATH/out/leaf_cert.pkcs8
}

function quic_client {
    build quic_client
    run_cmd $OUT_DIR/quic_client \
        --disable_certificate_verification=True \
        --host=$HOST \
        --port=$PORT \
        $SITE
}

function quic_chrome {
    RED_PORT=443   
 
    run_cmd google-chrome \
        --user-data-dir=/tmp/chrome-profile \
        --no-proxy-server \
        --enable-quic \
        --origin-to-force-quic-on=$SITE:$RED_PORT \
        --ignore-certificate-errors \
        --allow-running-insecure-content \
        --host-resolver-rules="'""MAP $SITE:$RED_PORT $HOST:$PORT""'" \
        --enable-features=NetworkService \
        https://$SITE
}

function usage() {
    echo "Usage: $0 [OPTION]..."
    echo "Quic runner."

    echo -e "\nOptions: "
    printf "\t %- 30s %s\n" "-s | --server" "Run a quic server."
    printf "\t %- 30s %s\n" "-c | --client" "Run a quic client."
    printf "\t %- 30s %s\n" "--port" "Change the port. (deafult 6121)"
    printf "\t %- 30s %s\n" "--site" "Change the site. (default www.example.org)"

    echo -e "\nExamples: "
    printf "\t %- 30s %s\n" "run.sh -s --site www.example.org"
    printf "\t %- 30s %s\n" "run.sh -c --port 6333 --site www.example.org"
}


function parse_command_line_options() {
    while [ "${1:-}" != "" ]; do
        case $1 in
            -b | --build)
                shift
                build net
                build quic_client
                build quic_server
                exit 0
                ;;
            -c | --client)
                shift
                FUNC=quic_client
                ;;
            -s | --server)
                shift
                FUNC=quic_server
                ;;
            --chrome)
                shift
                FUNC=quic_chrome
                ;;
            --host)
                shift
                HOST=$1
                ;;
            --port)
                shift
                PORT=$1
                ;;
            --site)
                shift 
                SITE=$1
                ;;
            -h | --help )
                usage
                exit 0
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
