from fastapi import Header


async def get_client_header(client: str = Header(...)):
    return client