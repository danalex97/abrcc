This repository provides a set of tools to:
1) run video streaming experiments with different ABR algorithms
1) visually analyze the ABR decisions from logfiles

## Getting started
To get started, first make sure you have the following python packets installed:

```sudo python -m pip install subprocess argparse numpy pyvirtualdisplay signal sys os psutil json logging sys sleep threading datetime traceback matplotlib selenium operator string math time```

Copy html folder to '/var/www/html'. 

Change personal names in dash.all.min_udp.js and proxy_server.py. 

Also, change directory for chrome driver in gamze_run_browser_test.py.

### Run an experiment
To test multiple ABRs in parallel we provide the "gamze_competitive_tests.py" script. 

```python gamze_competitive_tests.py config.json testcaseA.json testcaseB.json```

The config.json lets the script know the IP/Domain and Port of the cubic/bbr server and the network device which is used to limit the traffic (e.g. eth0). 

The other parameters are the paths to the testcases.
The results will be stored in the "testresults" folder where for each testcase a seperate folder is created.

Testcases are described in json format. Here is an example:
```java
{
    "test_id":"101_GAMZE_2streams_4.8Mbps",   //This will be the name of the folder containing the results
    "comment":"two GAMZE fighting for 4.8Mbps, one arriving 30s later",
    "trace":"4.8Mbps",                        //The network trace which should be used during the test. This file must exist in network_traces/
    "video":"testVideo",
    "repeat_n":"1",                           //number of repetitions 
    
    "jobs":[
        {
            "name":"GAMZE1",                  //this name must be unique within the job list
            "abr":"GAMZE",
            "quic":"false",
            "transport":"cubic"
            "start":"0",
            "duration":"200"
        },
        {
            "name":"GAMZE2",
            "abr":"GAMZE",
            "quic":"false",
            "transport":"cubic",
            "start":"30",
            "duration":"230"
        }
    ] 
}
```

To use LIMIT algorithm, change video server in gamze_competitive_test.py from gamze_video_server.py to gamze_video_server_limit.py.

## Create Plots from Logfiles

Use the following command to visualize a logfile:
```python plotresults.py /path/to/logfileA /path/to/logifleB```

Check the VideoStreaming_GamzeIslamoglu.pdf for further details.
