from server import component, JSONType


@component
async def log_metrics(json: JSONType) -> JSONType:
    return 'OK'
