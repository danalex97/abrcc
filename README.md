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

### Relevant source files

for adding new congestion control or abr functionality.

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
