from server.server import Component, JSONType
from abr.video import get_video_chunks, get_chunk_size
from abr.video import get_max_video_bit_rate, get_video_bit_rate
from abr.video import get_nbr_video_bit_rate
from abr import a3c

from pathlib import Path

import numpy as np
import tensorflow as tf
import os


S_INFO = 6  
S_LEN = 8  
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
    def __init__(self, video: str)-> None:
        super().__init__()
        
        sess = tf.Session()

        # save video name
        self.video = video
        self.adim = get_nbr_video_bit_rate(video)

        # actor and critic
        self.actor = a3c.ActorNetwork(sess,
            state_dim=[S_INFO, S_LEN], action_dim=self.adim,
            learning_rate=ACTOR_LR_RATE)
        self.critic = a3c.CriticNetwork(sess,
            state_dim=[S_INFO, S_LEN],
            learning_rate=CRITIC_LR_RATE)

        # load the pretained model
        saver = tf.train.Saver()
        directory = Path(os.path.dirname(os.path.realpath(__file__)))
        saver.restore(sess, f"{directory}/{NN_MODEL}")

        init_action = np.zeros(self.adim)
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

        reward = (get_video_bit_rate(self.video, last_quality) / M_IN_K 
                - REBUF_PENALTY * rebuffer_time / M_IN_K 
                - SMOOTH_PENALTY * np.abs(get_video_bit_rate(self.video, last_quality) 
                                          - last_bit_rate) / M_IN_K)

        # retrieve previous state
        if len(self.s_batch) == 0:
            state = [np.zeros((S_INFO, S_LEN))]
        else:
            state = np.array(self.s_batch[-1], copy=True)

        # compute bandwidth measurement
        bandwidth = max(float(json['bandwidth']), MIN_BW_EST_MBPS * M_IN_K)
        chunk_fetch_time = float(json['last_fetch_time']) 

        # compute number of video chunks left
        video_chunk_remain = get_video_chunks(self.video) - self.video_chunk_count
        self.video_chunk_count += 1

        # dequeue history record
        state = np.roll(state, -1, axis=1)
        next_video_chunk_sizes = []
        for i in range(self.adim):
            next_video_chunk_sizes.append(get_chunk_size(
                self.video, i, self.video_chunk_count
            ))

        total_buffer = float(json['buffer'])
        # this should be S_INFO number of terms
        try:
            state[0, -1] = (
                get_video_bit_rate(self.video, last_quality) / 
                get_max_video_bit_rate(self.video)
            )
            state[1, -1] = total_buffer / M_IN_K / BUFFER_NORM_FACTOR # s
            state[2, -1] = bandwidth / M_IN_K / 8 # k byte / ms
            state[3, -1] = float(chunk_fetch_time) / M_IN_K / BUFFER_NORM_FACTOR # 10 s 
            state[4, :self.adim] = np.array(next_video_chunk_sizes) / M_IN_K / M_IN_K # m byte  
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
        self.last_bit_rate = get_video_bit_rate(self.video, last_quality)
        self.last_quality = bit_rate
        return {
            'decision' : float(bit_rate),
        }
