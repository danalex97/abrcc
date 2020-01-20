from server.server import Component, JSONType
from abr.video import TOTAL_VIDEO_CHUNKS, VIDEO_BIT_RATE, get_chunk_size
from abr import a3c

from pathlib import Path

import numpy as np
import tensorflow as tf
import os


S_INFO = 6  
S_LEN = 8  
A_DIM = 6
BITRATE_REWARD = [1, 2, 3, 12, 15, 20]
BITRATE_REWARD_MAP = {0: 0, 300: 1, 750: 2, 1200: 3, 1850: 12, 2850: 15, 4300: 20}
M_IN_K = 1000.0
BUFFER_NORM_FACTOR = 10.0
CHUNK_TIL_VIDEO_END_CAP = 48.0
DEFAULT_QUALITY = 0  
REBUF_PENALTY = 4.3  
SMOOTH_PENALTY = 1
ACTOR_LR_RATE = 0.0001
CRITIC_LR_RATE = 0.001
TRAIN_SEQ_LEN = 100 
MODEL_SAVE_INTERVAL = 100
RANDOM_SEED = 42
RAND_RANGE = 1000
MIN_BW_EST_MBPS = 0.1
MIN_BW_EST_MBPS = 0.1


NN_MODEL = '/results/pretrain_linear_reward.ckpt'


class Pensieve(Component):
    def __init__(self)-> None:
        sess = tf.Session()

        # actor and critic
        self.actor = a3c.ActorNetwork(sess,
            state_dim=[S_INFO, S_LEN], action_dim=A_DIM,
            learning_rate=ACTOR_LR_RATE)
        self.critic = a3c.CriticNetwork(sess,
            state_dim=[S_INFO, S_LEN],
            learning_rate=CRITIC_LR_RATE)

        # load the pretained model
        saver = tf.train.Saver()
        directory = Path(os.path.dirname(os.path.realpath(__file__)))
        saver.restore(sess, f"{directory}/{NN_MODEL}")

        init_action = np.zeros(A_DIM)
        init_action[DEFAULT_QUALITY] = 1

        self.s_batch = [np.zeros((S_INFO, S_LEN))]
        self.a_batch = [init_action]
        self.r_batch = []
   
        self.train_counter = 0
        self.last_bit_rate = DEFAULT_QUALITY
        self.last_total_rebuf = 0
        self.video_chunk_count = 0

        self.last_rebuffer_time = 0
        self.last_quality = 0
        self.last_bit_rate = 0

    async def process(self, json: JSONType) -> JSONType:
        total_rebuffer = float(json['rebuffer']) / M_IN_K

        # compute data
        rebuffer_time = total_rebuffer - self.last_rebuffer_time
        last_quality = self.last_quality
        last_bit_rate = self.last_bit_rate

        reward = (VIDEO_BIT_RATE[last_quality] / M_IN_K 
                - REBUF_PENALTY * rebuffer_time / M_IN_K 
                - SMOOTH_PENALTY * np.abs(VIDEO_BIT_RATE[last_quality] - last_bit_rate) / M_IN_K)

        # retrieve previous state
        if len(self.s_batch) == 0:
            state = [np.zeros((S_INFO, S_LEN))]
        else:
            state = np.array(self.s_batch[-1], copy=True)

        # compute bandwidth measurement
        bandwidth = max(float(json['bandwidth']), MIN_BW_EST_MBPS * M_IN_K)
        chunk_fetch_time = float(json['last_fetch_time']) 

        # compute number of video chunks left
        video_chunk_remain = TOTAL_VIDEO_CHUNKS - self.video_chunk_count
        self.video_chunk_count += 1

        # dequeue history record
        state = np.roll(state, -1, axis=1)
        next_video_chunk_sizes = []
        for i in range(A_DIM):
            next_video_chunk_sizes.append(get_chunk_size(i, self.video_chunk_count))

        total_buffer = float(json['buffer'])
        # this should be S_INFO number of terms
        try:
            state[0, -1] = VIDEO_BIT_RATE[last_quality] / float(np.max(VIDEO_BIT_RATE))
            state[1, -1] = total_buffer / M_IN_K / BUFFER_NORM_FACTOR # s
            state[2, -1] = bandwidth / M_IN_K / 8 # k byte / ms
            state[3, -1] = float(chunk_fetch_time) / M_IN_K / BUFFER_NORM_FACTOR # 10 s 
            state[4, :A_DIM] = np.array(next_video_chunk_sizes) / M_IN_K / M_IN_K # m byte  
            state[5, -1] = np.minimum(video_chunk_remain, CHUNK_TIL_VIDEO_END_CAP) / float(CHUNK_TIL_VIDEO_END_CAP)
            print(state[:, -1])
        except ZeroDivisionError:
            if len(self.s_batch) == 0:
                state = [np.zeros((S_INFO, S_LEN))]
            else:
                state = np.array(self.s_batch[-1], copy=True)

        action_prob = self.actor.predict(np.reshape(state, (1, S_INFO, S_LEN)))
        action_cumsum = np.cumsum(action_prob)
        bit_rate = (action_cumsum > np.random.randint(1, RAND_RANGE) / float(RAND_RANGE)).argmax()
        
        self.s_batch.append(state)
        print(f"[Pensieve] > bit rate {bit_rate}")

        self.last_rebuffer_time = total_rebuffer
        self.last_bit_rate = VIDEO_BIT_RATE[last_quality] 
        self.last_quality = bit_rate
        return {
            'decision' : float(bit_rate),
        }
