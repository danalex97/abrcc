/* eslint-disable */
/* node.js script for passing arguments to dist/config.json */
'use strict';

const WARN = '\x1b[33m%s\x1b[0m';  

const { exec } = require('child_process');
const fs = require('fs');


function run_cmd(cmd) {
    exec(cmd, function(err, stdout, stderr) {
        log_out(err, stdout, stderr);

        if (err !== undefined && err !== null) {
            console.log(WARN, "> command failed: ");
            console.log('   ', cmd);
            process.exit(0);
        }
    });
}


function log_out(err, stdout, stderr) {
    if (stdout !== undefined && stdout !== null) {
        console.log(stdout);
    }
    if (stderr !== undefined && stderr !== null && stderr !== "") {
        console.warn(stderr);
    }
}


let args = process.argv.slice(2);
console.log("> running build with arguments: ", args)


let data = JSON.stringify({
    "args": args,
});
fs.writeFileSync('dist/config.json', data);
console.log("> config generated");

// Running the build process via npm
run_cmd("npm run compile");
run_cmd("npm run lint");
run_cmd("npm run build:run");
