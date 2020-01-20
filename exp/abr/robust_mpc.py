import statistics
import itertools
import timeit

from typing import List

from abr.video import TOTAL_VIDEO_CHUNKS, VIDEO_BIT_RATE, get_chunk_size
from server.server import Component, JSONType


M_IN_K = 1000.0
REBUF_PENALTY = 4.3
SMOOTH_PENALTY = 1
HORIZON = 5
SEGMENT_SIZE = 4
MIN_BW_EST_MBPS = 0.1


class RobustMpc(Component):
    def __init__(self)-> None:
        self.last_rebuffer_time: float = 0
        self.last_bit_rate: float = 0
        self.last_quality: int = 0

        self.bandwidths: List[float] = []
        self.past_bandwidth_ests: List[float] = []
        self.past_errors: List[float] = []

    async def process(self, json: JSONType) -> JSONType:
        start = timeit.timeit()
        
        print(f"[robustMpc] > serving {json}")
        total_rebuffer = float(json['rebuffer']) / M_IN_K
        last_quality = self.last_quality
        last_bit_rate = self.last_bit_rate
        
        rebuffer_time = total_rebuffer - self.last_rebuffer_time
        smooth_diff = abs(VIDEO_BIT_RATE[last_quality] - last_bit_rate)

        # compute reward
        reward = (VIDEO_BIT_RATE[last_quality] / M_IN_K 
                  - REBUF_PENALTY * rebuffer_time / M_IN_K
                  - SMOOTH_PENALTY * smooth_diff / M_IN_K)
        
        # update state
        self.last_bit_rate = VIDEO_BIT_RATE[last_quality] 
        self.last_rebuffer_time = total_rebuffer 

        # compute bandwidth measurement  
        bandwidth = max(float(json['bandwidth']) / M_IN_K, MIN_BW_EST_MBPS)
        self.bandwidths.append(bandwidth)

        # compute number of video chunks left
        index = json['index']
        video_chunk_remain = TOTAL_VIDEO_CHUNKS - index

        # past error
        if len(self.past_bandwidth_ests) == 0:
            self.past_errors.append(0)
        else:
            curr_error = abs(self.past_bandwidth_ests[-1] - bandwidth) / bandwidth
            self.past_errors.append(curr_error)

        # past bandwidths 
        harmonic_bandwidth = statistics.harmonic_mean(self.bandwidths[-HORIZON:])       
        max_error = max(self.past_errors[-HORIZON:])
       
        future_bandwidth = max(harmonic_bandwidth / (1 + max_error), MIN_BW_EST_MBPS)
        self.past_bandwidth_ests.append(harmonic_bandwidth)
        print(f"[robustMpc] > future bandwidth {future_bandwidth}")

        # max reward
        start_buffer = float(json['buffer']) / M_IN_K 
        print(f"[robustMpc] > current buffer {start_buffer}")
        max_reward, best_rate = 0, 0
        for full_combo in itertools.product(range(len(VIDEO_BIT_RATE)), repeat=HORIZON):
            combo = full_combo[:min(TOTAL_VIDEO_CHUNKS - index, HORIZON)]

            curr_rebuffer_time = 0
            curr_buffer = start_buffer
            bitrate_sum = 0
            smoothness_diff = 0
            last_quality = self.last_quality
            
            for position in range(len(combo)):
                chunk_quality = combo[position]
                curr_index = index + position

                size = 8 * get_chunk_size(chunk_quality, curr_index) / M_IN_K ** 2 # in mb
                download_time = size / future_bandwidth # in s

                # simulate future buffer
                if curr_buffer < download_time:
                    curr_rebuffer_time += download_time - curr_buffer
                    curr_buffer = 0
                else:
                    curr_buffer -= download_time
                curr_buffer += SEGMENT_SIZE
                
                # linear reward for the buffer
                bitrate_sum += VIDEO_BIT_RATE[chunk_quality]
                smoothness_diff += abs(VIDEO_BIT_RATE[chunk_quality] 
                                        - VIDEO_BIT_RATE[last_quality])
                
                last_quality = chunk_quality

            # total reward for whole simualtion
            reward = ( bitrate_sum / M_IN_K
                     - REBUF_PENALTY * curr_rebuffer_time
                     - smoothness_diff / M_IN_K )
            if reward > max_reward:
                max_reward = reward
                best_rate = combo[0]

        self.last_quality = best_rate
        print(f"[robustMpc] > decision {best_rate}")
        
        end = timeit.timeit()
        print(f"[robustMpc] > time {end - start}")

        return {
            'decision' : best_rate,
        }
