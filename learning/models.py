from abc import abstractmethod, ABC
from collections import deque
from typing import List, Tuple, Dict

from keras.layers import Dense
from keras.models import Sequential
from keras.optimizers import Adam

import random
import keras
import numpy as np
import tensorflow as tf
from tensorflow.python.keras.backend import set_session


sess = tf.Session()
set_session(sess)
graph = tf.get_default_graph()


UPDATE_TARGET_EVERY = 50
INPUT_VECTOR_SIZE  = 56
REPLAY_MEMORY_SIZE = 2_000
MIN_REPLAY_MEMORY_SIZE = 5
MINIBATCH_SIZE = 5
OUTPUT_SPACE = 30
DISCOUNT = .8


# input_vector, action, rewards, new_input_vector
Transition = Tuple[np.array, int, float, np.array]


class Model(ABC):
    @abstractmethod
    def predict(self, input_vector: List[int]) -> int:
        pass

    @abstractmethod
    def update_replay_memory(self, 
        input_vector: List[int], 
        action: int,
        reward: Dict[str, float],
        new_input_vector: List[int],
    ) -> None:
        pass

    @abstractmethod
    def train(self) -> None:
        pass


class DummyModel(Model):
    def predict(self, input_vector: List[int]) -> int:
        return 1

    def update_replay_memory(self, 
        input_vector: List[int], 
        action: int,
        reward: Dict[str, float],
        new_input_vector: List[int],
    ) -> None:
        pass

    def train(self) -> None:
        pass

class SimpleNNModel(Model):
    @staticmethod
    def create_model() -> Sequential:
        model = Sequential()
        model.add(Dense(200, activation='relu', input_dim = INPUT_VECTOR_SIZE))
        model.add(Dense(100, activation='relu'))
        model.add(Dense(OUTPUT_SPACE, activation='relu'))
        model.compile(loss="mse", optimizer=Adam(lr=0.001), metrics=['accuracy'])
        return model
    
    def __init__(self):
        # main model
        self.model: Sequential = self.create_model()
        
        # target model
        self.target_model: Sequential = self.create_model()
        self.target_model.set_weights(self.model.get_weights())

        # replay memory
        self.replay_memory: List[Transition] = deque(maxlen=REPLAY_MEMORY_SIZE)
        self.target_update_counter = 0
        
        # counter
        self.counter = 0

    def predict(self, input_vector: List[int]) -> int:
        with sess.as_default():
            with graph.as_default():
                input_vector = np.asarray(input_vector)
                qs: np.array = self.model.predict(input_vector.reshape(1,-1))
                return np.argmax(qs)

    def update_replay_memory(self, 
        input_vector: List[int], 
        action: int,
        reward: Dict[str, float],
        new_input_vector: List[int],
    ) -> None:
        total_reward: float = sum(reward.values())
        self.replay_memory.append(
            (np.asarray(input_vector), action, total_reward, np.asarray(new_input_vector))
        )

    def train(self) -> None:
        for t in range(max(1, len(self.replay_memory) // MINIBATCH_SIZE // 2)): 
            with sess.as_default():
                with graph.as_default():
                    # start training only after a certain number of samples
                    if len(self.replay_memory) < MIN_REPLAY_MEMORY_SIZE:
                        return

                    print(f'Training epoch {self.counter}')
                    self.counter += 1

                    # get minibatch
                    minibatch = random.sample(self.replay_memory, MINIBATCH_SIZE)
                    
                    # get current states from minibatch
                    current_states = np.array([transition[0] for transition in minibatch])
                    current_qs_list = self.model.predict(current_states) 

                    # get future states from minibatch, then query NN model for Q values
                    # when using target network, query it, otherwise main network should be queried
                    new_current_states = np.array([transition[3] for transition in minibatch])
                    future_qs_list = self.target_model.predict(new_current_states)

                    # training data
                    X: List[np.ndarray] = []
                    y: List[np.array] = []
                    for index, (current_state, action, reward, new_current_state) in enumerate(minibatch):
                        # best q-value - that is the q-value of best output action possible 
                        max_future_q: np.ndarray = np.max(future_qs_list)
                        new_q: np.ndarray = reward + DISCOUNT * max_future_q

                        # update q for given state
                        current_qs: np.array = current_qs_list[index] # q-values for current state
                        current_qs[action] = new_q
                        
                        # append to training data
                        X.append(current_state)
                        y.append(current_qs)

                    # fit on all sample as one batch
                    self.model.fit(np.array(X), np.array(y), batch_size=MINIBATCH_SIZE, verbose=0, shuffle=False)

                    # update target network counter
                    self.target_update_counter += 1
                    
                    # update network weights every 
                    if self.target_update_counter > UPDATE_TARGET_EVERY:
                        self.target_model.set_weights(self.model.get_weights())
                        self.target_update_counter = 0
