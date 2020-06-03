from typing import List

from flask import Flask
from flask import request

import json


app = Flask(__name__)


@app.route('/target_bandwidth')
def get_target_bandwidth():
    avg_bandwidth: int = int(request.args.get('avg_bandwidth'))
    current_bandwidth: int = int(request.args.get('current_bandwidth'))
    last_buffer: int = int(request.args.get('last_buffer'))
    last_rtt: int = int(request.args.get('last_rtt')) 

    vmafs: List[List[int]] = eval(request.args.get('vmafs'))
    sizes: List[List[int]] = eval(request.args.get('sizes'))

    current_quality: int = int(request.args.get('current_quality'))
    current_index: int = (request.args.get('current_index'))
    current_vmaf: int = vmafs[0][current_quality - 1]
    current_size: int = sizes[0][current_quality - 1]

    print(avg_bandwidth)
    print(current_bandwidth)
    print(last_buffer)
    print(last_rtt)
    print(current_vmaf)
    print(current_size)
    print(vmafs)
    print(sizes)

    return "1"


@app.route('/reward', methods=['POST'])
def get_rewards():
    data = json.loads(request.data)

    name: str = data['name']
    qoe: float = data['qoe']
    index: int = data['index']
    
    print(name, index, qoe)

    return "OK"


if __name__ == '__main__':
    app.run()
