from typing import List, Mapping, Union


JSONType = Union[str, int, float, bool, None, Mapping[str, 'JSONType'], List['JSONType']]


class Value:
    """
    Timestamped floating point value.
    """
    def __init__(self, value: float, timestamp: int) -> None:
        self.value = value
        self.timestamp = timestamp

    @staticmethod
    def from_json(json: JSONType) -> 'Value':
        return Value(json['value'], json['timestamp'])

    @property
    def json(self) -> JSONType:
        return {
            'value' : self.value,
            'timestamp' : self.timestamp,
        }

    def __str__(self) -> str:
        return f"Value({self.value}; {self.timestamp})"
    
    def __repr__(self) -> str:
        return self.__str__()


class Segment:
    """
    Segment metadata. 
      - index: the segment index
      - state: loading, progress or downloaded
      - quality: integer representing the quality track
      - timestamp: front-end integer timestamp
    """
    LOADING = "loading"

    def __init__(self, index: int, state: str, quality: int, timestamp: int) -> None:
        self.index = index
        self.state = state
        self.quality = quality
        self.timestamp = timestamp

    @staticmethod
    def from_json(json: JSONType) -> 'Segment':
        return Segment(json['index'], json['state'], json['quality'], json['timestamp'])

    @property
    def json(self) -> JSONType:
        return {
            'index' : self.index,
            'state' : self.state,
            'quality' : self.quality,
            'timestamp' : self.timestamp,
        }
    
    @property
    def loading(self) -> bool:
        return self.state == self.LOADING

    def __str__(self) -> str:
        return f"Segment(index: {self.index}, quality: {self.quality}, {self.state}; {self.timestamp})" 

    def __repr__(self) -> str:
        return self.__str__()


class Metrics:
    """
    Front-end generated metrics. The same data format as specified in `dash/common/data`.
    """
    def __init__(self, 
        droppedFrames: List[Value], 
        playerTime: List[Value],  
        bufferLevel: List[Value],
        segments: List[Segment],
    ) -> None:
        self.droppedFrames = droppedFrames
        self.playerTime = playerTime
        self.bufferLevel = bufferLevel
        self.segments = segments

    @staticmethod
    def from_json(json: JSONType) -> 'Metrics':
        return Metrics(
            [Value.from_json(x) for x in json['droppedFrames']],
            [Value.from_json(x) for x in json['playerTime']],
            [Value.from_json(x) for x in json['bufferLevel']],
            [Segment.from_json(x) for x in json['segments']],
        )
    
    @property 
    def timestamp(self) -> int:
        return max([v.timestamp for v in self.playerTime], default=0)

    @property
    def json(self) -> JSONType:
        return {
            'droppedFrames' : [x.json for x in self.droppedFrames],
            'playerTime' : [x.json for x in self.playerTime],
            'bufferLevel' : [x.json for x in self.bufferLevel],
            'segments' : [x.json for x in self.segments]
        }

    def __str__(self) -> str:
        return (f"Metrics(droppedFrames: {self.droppedFrames}, " +
               f"playerTime: {self.playerTime}, " +
               f"bufferLevel: {self.bufferLevel}, " +
               f"segments: {self.segments})")

    def __repr__(self) -> str:
        return self.__str__()
