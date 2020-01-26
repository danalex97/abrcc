# ABR-CC

### Installation

To install the Chromium CC server one can run:
```
quic/install.sh --install
```

To install all Python dependencies, run:
```
pip3 install -r exp/requirements.txt
```

To install the Javascript dependencies, run from the folder `dash`:
```
npm install
```

### Running an experiment

To run an individual experiment, from folder `exp` use the script:
```
python3 run.py -h
```

To create a more complex experiment, add Python code in `exp/experiments.py`. Then one can run an experiment from the folder `exp` via:
```
python3 experiment/py -h
```

### Running individual components

#### QUIC

A QUIC server can be run independently via:
```
quic/run.sh -s
```

To open a Chrome instance, use:
```
quic/run.sh --chrome
```

To only build the C++ modules, one can run:
```
quic/run.sh -b
```

If a script is stopped in the middle of the build, to arrive in the correct state, run:
```
quic/install.sh --build
```

#### DASH

When only trying to develop on the front-end it may be useful to lint and build directly. From the directory `dash`, one can run:

```
npm run lint
npm run build [build-arguments]
```

### Adding new CC/ABR functionality

For adding new congestion control or abr functionality, the following files should be relevant:

```
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
    +-- experiment.py
    +-- plot.py
```

#### Adding a new ABR algorithm

To add an ABR algorithm in the front-end, add a new file in `dash/src/algo` and implement the interface from `dash/src/algo/interface.js`.

To add an ABR algorithm in the back-end, implement the interface `AbrInterface` from the file `quic/chromium/src/net/abrcc/abr/interface.h`.

#### Adding a new CC algorithm
  - add a new algorithm in enumeration from `net/third_party/quiche/src/quic/core/quic_types.h`
  - implement the new algorithm by implementing the methods that `quic/chromium/src/net/abrcc/cc/cc_wrapper.cc` implements
  - add the new algorithm in `quic/chromium/src/net/abrcc/cc/cc_selector.cc`
  - add the new algorithm in `quic/run.sh`
  - add the new algorithm in `exp/run.sh`
