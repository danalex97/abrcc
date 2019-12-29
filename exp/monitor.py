from server import component, JSONType


@component
async def log_metrics(json: JSONType) -> JSONType:
    print(json['stats'])
    return 'OK'
