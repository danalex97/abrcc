import aiohttp
import asyncio
import copy
import json
import random
import string

from abc import ABC, abstractmethod
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, List, Union

from quart import Quart, request as quart_request
from quart_cors import cors as quart_cors

from sanic import Sanic, request as sanic_request, response as sanic_response
from sanic_cors import CORS as sanic_cors

from .data import JSONType


class UncompatibleBackendError(NotImplementedError):
    pass


class Backend(Enum):
    SANIC = 0
    QUART = 1


async def post_after(data: JSONType, wait: int, resource: str, port: int = 8080) -> None:
    """
    Send a JSON after wait ms.
    """
    await asyncio.sleep(wait / 1000)
    if resource[0] == '/':
        resource = resource[1:]
    url = f"https://127.0.0.1:{port}/{resource}"
    async with aiohttp.ClientSession() as client:
        async with client.post(url, data=json.dumps(data), verify_ssl=False):
            pass


def post_after_async(data: JSONType, wait: int, resource: str, port: int = 8080) -> None:
    """
    Best effor send JSON after at least wait ms.
    """
    asyncio.ensure_future(post_after(data, wait, resource, port))


class Component(ABC):
    """
    A component class that receives JSON requests and returns stringyfied jsons.
    To implement a new component, extend this class.
    
    Example usage:
    class MyComp(Component):
        async def process(self, json: JSONType) -> JSONType:
            return 'OK'
    """
    @abstractmethod
    async def process(self, json: JSONType) -> JSONType:
        pass

    @staticmethod
    def get_req(data: Union[bytes, str]) -> JSONType:
        if type(data) == bytes:
            data = data.decode('ascii')
        try:
            req = json.loads(data) 
        except: 
            req = data
        return req

    async def receive_quart(self) -> str:
        req = await quart_request.get_json()
        if req is None:
            data = await quart_request.get_data()
            req  = self.get_req(data)
        out = await self.process(req)
        return str(out) 

    async def receive_sanic(self, request: sanic_request) -> sanic_response.json:
        req = request.json
        if req is None:
            data = request.body
            req  = self.get_req(data)
        out = await self.process(req)
        return sanic_response.json(out) 


def component(f: Callable[[JSONType], Awaitable[JSONType]]) -> Component:
    """
    Create a component from a function.
    """
    class __comp(Component):
        async def process(self, json: JSONType) -> JSONType:
            return await f(json)
    return __comp()


@component
async def do_nothing(json: JSONType) -> JSONType:
    return 'OK'


def ctx_component(f: Callable[[Any, JSONType], Awaitable[JSONType]]) -> Component:
    """
    Create a component from a class function.
    """
    def wrapper(ctx: Any) -> Component:
        class __comp(Component):
            async def process(self, json: JSONType) -> JSONType:
                return await f(ctx, json)
        return __comp()
    return wrapper


def multiple(*components: Component) -> Component:
    """
    Run multiple components and return OK.
    """
    class __comp(Component):
        async def process(self, json: JSONType) -> JSONType:
            await asyncio.gather(*[c.process(copy.deepcopy(json)) for c in components])
            return 'OK'

    return __comp()


def multiple_sync(*components: Component) -> Component:
    """
    Run multiple components and return OK.
    """
    class __comp(Component):
        async def process(self, json: JSONType) -> JSONType:
            for c in components:
                await c.process(copy.deepcopy(json))
            return 'OK'

    return __comp()


class Server:
    """
    A server builder class.

    Each server is extendable via adding restful components.
    The underlying server can be either Quart or Sanic.
    
    Example usage:
    (Server('example', 8008, Backend.QUART)
        .add_get('/double', component(lambda x: int(x) * 2))
        .add_get('/ok', component(lambda x: 'OK'))
        .run())
    """
    components: List[Component]

    def __init__(self, name: str, port: int, backend: Backend = Backend.SANIC) -> None:
        if backend is Backend.SANIC:
            self.__app = Sanic(name)
            sanic_cors(self.__app, automatic_options=True)
        elif backend is Backend.QUART:
            self.__app = quart_cors(Quart(name))

        self.__backend = backend
        self.__name = name
        self.__port = port
        self.components = []

    def __add_method(self, 
        route: str, 
        component: Component, 
        method: str,
    ) -> 'Server':
        self.components.append(component)
        random_id = ''.join(random.choice(
            string.ascii_uppercase + string.ascii_lowercase) 
            for _ in range(10)
        )
        component_name = self.__name + random_id + route.replace("/", "_")
    
        def binder():
            if self.__backend is Backend.SANIC:
                def binded(request):
                    return component.receive_sanic(request)
                binded.__name__ = component_name
                return binded
            elif self.__backend is Backend.QUART:
                def binded():
                    return component.receive_quart()
                binded.__name__ = component_name
                return binded
            else:
                raise UncompatibleBackendError()
        self.__app.route(route, methods=[method, 'OPTIONS'])(binder())
        return self

    def add_get(self, route: str, component: Component) -> 'Server':
        return self.__add_method(route, component, 'GET')
    
    def add_post(self, route: str, component: Component) -> 'Server':
        return self.__add_method(route, component, 'POST')

    def run(self):
        if self.__backend is Backend.SANIC:
            self.__app.run(
                host='0.0.0.0', 
                port=int(self.__port),
                ssl={
                    'cert' : 'certs/cert.pem',
                    'key' : 'certs/key.pem',
                },
            )
        elif self.__backend is Backend.QUART:
            self.__app.run(
                host='0.0.0.0', 
                port=int(self.__port),
                certfile='certs/cert.pem',
                keyfile='certs/key.pem',
            )
        else:
            raise UncompatibleBackendError()
