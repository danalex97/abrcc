from server.server import Component, JSONType


class Pensieve(Component):
    def __init__(self)-> None:
        pass
    
    async def process(self, json: JSONType) -> JSONType:
        return {
            'decision' : 5,
        }
