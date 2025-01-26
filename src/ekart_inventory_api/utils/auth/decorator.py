from functools import wraps
from typing import List

from fastapi import Depends, HTTPException, Request


def require_permissions(required_permissions: List[tuple]):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request = Depends(), **kwargs):
            if not hasattr(request.state, "permissions"):
                raise HTTPException(status_code=403, detail="No permissions found")

            user_permissions = request.state.permissions

            for action, module in required_permissions:
                if (action, module) not in user_permissions:
                    raise HTTPException(status_code=403, detail="Permission denied")

            return await func(*args, request=request, **kwargs)

        return wrapper

    return decorator
