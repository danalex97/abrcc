# Cross-layer Adaptive Bitrate Streaming

The project contains a set of cross-layer adaptive bitrate streaming algorithms implemented on top of [QUIC](https://www.chromium.org/quic) and [DASH.js](https://github.com/Dash-Industry-Forum/dash.js).

### Repository structure

* **quic**: Chromium QUIC server with pluggable congestion control and adaptive bitrate algorithms
* **dash**: Typescript(and ECMAScript 6) wrapper over DASH.js player
* **exp**: Experimental setup for running multiple players over a shared environment.
* **downloads**: Python scripts for downloading and preparing new videos.
* **learning**: Environment for reinforcement learning-based congestion control.

For more details about each sub-module, take a look at the README present in each folder.

### Quickstart

Experiment can be run from the script `exp/experiments.py`. To be able to do so, one needs to:
  - install the Chromium QUIC server:
    ```bash
    quic/install.sh --install
    ```
  - install the Python dependencies:
    ```bash
    pip3 install -r exp/requirements.txt
    ```
  - install front-end dependencies from the `dash` folder:
  ```bash
  npm install
  ```

The experiments can be listed using the command:
```bash
python3 exp/experiment.py --help
```

To run an experiment, one can use the command:
```bash
python3 exp/experiment.py --help
```


Note that the [TC Linux](https://man7.org/linux/man-pages/man8/tc.8.html) utility needs root privileges, hence running an experiment might need `sudo`.

### Algorithms

The list of available(CC and ABR) algorithms can be found using the command:
```bash
$ python3 exp/run.py --help

usage: run.py [-h] [...]
  [--algo {bola,dynamic,bb,festive,rb,robustMpc,pensieve,minerva,minervann}]
  [--server-algo {bb,random,worthed,target,target2,target3,gap,remote,minerva,minervann}]
  [--cc {bbr,bbr2,pcc,reno,cubic,abbr,xbbr,target,gap,minerva}]
```

The `--algo` argument shows all possible choices for in-player implemented ABR algorithms(i.e. implementations found in the `dash` folder), while `--server-algo` shows the possible choices for server-side ABR implementations. The `--cc` argument shows all possible server-side implementations.


In-player ABR algorithms:
  - [BOLA](https://ieeexplore.ieee.org/document/9110784): buffer-based algorithm provided in the DASH.js player
  - [Dynamic](https://dl.acm.org/doi/abs/10.1145/3336497): default DASH.js player
  - BB: simple buffer-based algorithm; [BBA](http://yuba.stanford.edu/~nickm/papers/sigcomm2014-video.pdf) simplified
  - [Festive](https://dl.acm.org/doi/10.1145/2413176.2413189): a rate-based approach that uses a windowed harmonic mean for bandwidth estimation
  - RB: simple rate-based algorithm; chooses quality proportional with last segment's download time bandwidth estimation
  - [RobustMpc](https://users.ece.cmu.edu/~vsekar/papers/sigcomm15_mpcdash.pdf): a control-theoretic rate-based approach for ABR; implementation is found in the `exp/abr` folder
  - [Pensieve](https://github.com/hongzimao/pensieve): adaptive bitrate algorithms using reinforcement learning
  - [Minerva](http://web.cs.ucla.edu/~ravi/CS219_F19/papers/minerva.pdf): end-to-
end transport for video QoE fairness; needs both `--algo` and `--server-algo` flags


Server-side ABR algorithms(mostly composed of our original custom CC-ABR combination algorithm):
  - **Random:** chooses random video quality for each segment
  - **Worthed:** VMAF-aware planning; found in `quic/chromium/src/net/abrcc/abr/abr_worthed.cc`
  - **Target:** low-liberty long-term planning ABR; found in  `quic/chromium/src/net/abrcc/abr/abr_target.cc`
  - **Gap:** Target-based ABR with specialized congestion-control; found in `quic/chromium/src/net/abrcc/abr/abr_gap.cc`
  - **Remote:** custom backend that exposes the CC and ABR internal states and listens for decisions from a 3rd party server


Congestion control algorithms:
  - Standard congestion control algorithms: Cubic, Reno, PCC, BBR, BBR2
  - Specialized algorithms: ABBR for Worthed, Target, Gap and Minerva


## Development

### Running experiments

- Individual experiments can be run from folder `exp` by:
```bash
python3 run.py -h
```
- More complex experiments(e.g. multiple instances, variable bandwidth traces, etc.) can be setup in Python code from the file `exp/experiments.py`; after setup, the experiments can be run by:
```bash
python3 experiment/py -h
```

### Running individual components

- To run a QUIC server:
```bash
quic/run.sh -s
```
- To open a Chrome instance running QUIC, use:
```bash
quic/run.sh --chrome
```
- To only build the C++ modules:
```bash
quic/run.sh -b
```
- If a script is stopped in the middle of the build, to arrive in the correct state, run:
```bash
quic/install.sh --build
```
- When only trying to develop on the front-end it may be useful to lint and build directly. From the directory `dash`, one can run:
```bash
npm run lint
npm run build [build-arguments]
```

### Adding new CC/ABR functionality

For adding new CC or ABR functionality, the following files should be relevant:
```bash
+-- quic
|   +-- chromium
|       +-- src/net
|           +-- abrcc
|           |   +-- abr
|           |   +-- cc   
|           |   +-- dash_backend.cc
|           |   +-- dash_server.cc
|           +-- BUILD.gn
+-- dash
|   +-- src
|       +-- algo       
|       |   +-- interface.js
|       |   +-- selector.js
|       +-- common        
|           +-- args.js  
+-- exp
    +-- abr
    +-- run.py
```

#### ► Adding a new ABR algorithm - Javascript
 - add a new file in `dash/src/algo` and implement the interface from `dash/src/algo/interface.js`
 - add the new algorithm in `exp/run.sh`

#### ► Adding a new ABR algorithm - Python
   - implement the interface `server.server.Component`
   - the output should be a JSON with the filed `decision`
   - add the new algorithm in `exp/run.sh`

#### ► Adding a new ABR algorithm - C++
  - implement the interface `AbrInterface` from the file `quic/chromium/src/net/abrcc/abr/interface.h`
  - add algorithm in function `getAbr` from file `quic/chromium/src/net/abrcc/abr/abr.cc`
  - add the new algorithm `quic/run.sh`
  - add the new algorithm in `exp/run.sh`

#### ► Adding a new CC algorithm
  - add a new algorithm in enumeration from `net/third_party/quiche/src/quic/core/quic_types.h`
  - implement the new algorithm by implementing the methods that `quic/chromium/src/net/abrcc/cc/cc_wrapper.cc` implements
  - add the new algorithm in `quic/chromium/src/net/abrcc/cc/cc_selector.cc`
  - add the new algorithm in `quic/run.sh`
  - add the new algorithm in `exp/run.sh`
