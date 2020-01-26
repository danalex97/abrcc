# ABR-CC

### Installation

To install the Chromium server one can run:
```bash
quic/install.sh --install
```

To install all Python dependencies, run:
```bash
pip3 install -r exp/requirements.txt
```

To install the Javascript dependencies, run from the folder `dash`:
```bash
npm install
```

### Running an experiment

To run an individual experiment, from folder `exp` use the script:
```bash
python3 run.py -h
```

To create a more complex experiment, add Python code in `exp/experiments.py`. Then one can run an experiment from the folder `exp` via:
```bash
python3 experiment/py -h
```

### Running individual components

A QUIC server can be run independently via:
```bash
quic/run.sh -s
```

To open a Chrome instance, use:
```bash
quic/run.sh --chrome
```

To only build the C++ modules, one can run:
```bash
quic/run.sh -b
```

If a script is stopped in the middle of the build, to arrive in the correct state, run:
```bash
quic/install.sh --build
```

When only trying to develop on the front-end it may be useful to lint and build directly. From the directory `dash`, one can run:

```bash
npm run lint
npm run build [build-arguments]
```

### Adding new CC/ABR functionality

For adding new congestion control or abr functionality, the following files should be relevant:

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

#### Adding a new ABR algorithm - Javascript
 - add a new file in `dash/src/algo` and implement the interface from `dash/src/algo/interface.js`
 - add the new algorithm in `exp/run.sh`

#### Adding a new ABR algorithm - Python
   - implement the interface `server.server.Component`
   - the output should be a JSON with the filed `decision`
   - add the new algorithm in `exp/run.sh`

#### Adding a new ABR algorithm - C++
  - implement the interface `AbrInterface` from the file `quic/chromium/src/net/abrcc/abr/interface.h`
  - add algorithm in function `getAbr` from file `quic/chromium/src/net/abrcc/abr/abr.cc`
  - add the new algorithm `quic/run.sh`
  - add the new algorithm in `exp/run.sh`

#### Adding a new CC algorithm
  - add a new algorithm in enumeration from `net/third_party/quiche/src/quic/core/quic_types.h`
  - implement the new algorithm by implementing the methods that `quic/chromium/src/net/abrcc/cc/cc_wrapper.cc` implements
  - add the new algorithm in `quic/chromium/src/net/abrcc/cc/cc_selector.cc`
  - add the new algorithm in `quic/run.sh`
  - add the new algorithm in `exp/run.sh`

#### CC-ABR interaction

Any singleton can be used for communication between CC and ABR:
```C++
#include "net/abrcc/cc/singleton.h"

class ExampleSingleton {
 public:
  void method() {
  }
}
```

Usage:
```C++
GET_SINGLETON(ExampleSingleton)->method();
```
