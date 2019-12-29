import json

from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Awaitable, Callable, List, Mapping, Union

from quart import Quart, request
from quart_cors import cors


JSONType = Union[str, int, float, bool, None, Mapping[str, 'JSONType'], List['JSONType']]


class Component(ABC):
    """
    A component class that receives JSON requests and returns stringyfied jsons.
    To implement a new component, extend this class.
    """
    @abstractmethod
    async def process(self, json: JSONType) -> JSONType:
        pass

    async def receive(self) -> str:
        req = await request.get_json()
        if req is None:
            data = await request.get_data()
            if type(data) == bytes:
                data = data.decode('ascii')
            try:
                req  = json.loads(data) 
            except: 
                req = data
        out = await self.process(req)
        return str(out) 


def component(f: Callable[[JSONType], Awaitable[JSONType]]) -> Component:
    """
    Create a component from a function.
    """
    class __comp(Component):
        async def process(self, json: JSONType) -> JSONType:
            return await f(json)
    return __comp()


class Server:
    """
    A server builder class.

    Each server is extendable via adding restful components.
    The underlying server is Quart.
    
    Example usage:
    (Server('example', 8008)
        .add_get('/double', component(lambda x: int(x) * 2))
        .add_get('/ok', component(lambda x: 'OK'))
        .run())
    """
    components: List[Component]

    def __init__(self, name: str, port: int) -> None:
        self.__app = cors(Quart(name))
        self.__name = name
        self.__port = port
        self.components = []

    def __add_method(self, 
        route: str, 
        component: Component, 
        method: str,
    ) -> 'Server':
        self.components.append(component)

        def binder():
            def binded():
                return component.receive()
            binded.__name__ = self.__name + route.replace("/", "_")
            return binded

        self.__app.route(route, methods=[method])(binder())
        return self

    def add_get(self, route: str, component: Component) -> 'Server':
        return self.__add_method(route, component, 'GET')
    
    def add_post(self, route: str, component: Component) -> 'Server':
        return self.__add_method(route, component, 'POST')

    def run(self):
        self.__app.run(
            host='0.0.0.0', 
            port=int(self.__port), 
            certfile='certs/cert.pem', 
            keyfile='certs/key.pem',    
        )
