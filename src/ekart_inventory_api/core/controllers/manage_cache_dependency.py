# from cachetools import TTLCache
# from fastapi import Depends, Request
# from sqlalchemy import select
# from sqlalchemy.ext.asyncio import AsyncEngine
# from starlette_context import context

# from .dependencies import get_client_header
# from ..controllers.developer.config_controller import ConfigController
# from ..models.police.police import Permission
# from utils.auth.auth_token_decoder import JWTAuthorizationCredentials, auth
# from utils.database.connections import get_async_engine
# from utils.database.session_context_manager import session_context

# roles_cache = TTLCache(maxsize=100, ttl=600)
# config_cache = TTLCache(maxsize=100, ttl=600)


# async def get_config(agency: str, controller: ConfigController):
#     config_data = await controller.get_client_config(agency)
#     group_config_by_section = controller.group_configs_based_on_section(config_data)

#     combined_config = {}
#     for config_section, values in group_config_by_section.items():
#         combined_config[config_section] = values.copy()
#     return combined_config


# async def make_permissions_cache(
#     agency: str,
#     roles: list,
#     async_engine: AsyncEngine,
#     refresh_permission_cache: bool = False,
# ) -> list[tuple]:
#     user_permissions = []
#     for role in roles:
#         if (agency, role) not in roles_cache or refresh_permission_cache:
#             async with session_context(async_engine, client_name=agency) as session:
#                 permissions = await session.execute(
#                     select(Permission.permission_action, Permission.module).where(
#                         Permission.user_role == role
#                     )
#                 )
#                 permissions_list = permissions.all()
#                 roles_cache[(agency, role)] = [
#                     (row.permission_action.strip(), row.module.strip())
#                     for row in permissions_list
#                 ]
#         user_permissions += roles_cache.get((agency, role)) or []
#     return user_permissions


# async def manage_request_state(
#     request: Request,
#     credentials: JWTAuthorizationCredentials = Depends(auth),
#     agency: str = Depends(get_client_header),
#     config_controller=Depends(ConfigController),
#     async_engine: AsyncEngine = Depends(get_async_engine),
# ):
#     user_permissions = await make_permissions_cache(
#         agency=agency, roles=credentials.roles, async_engine=async_engine
#     )

#     # Handle configuration cache
#     if agency not in config_cache:
#         config_cache[agency] = await get_config(
#             agency=agency, controller=config_controller
#         )

#     context.update(
#         {
#             "config": config_cache[agency],
#             "permissions": user_permissions,
#             "user_details": {
#                 "name": f"{credentials.first_name} {credentials.last_name}",
#                 "roles": credentials.roles,
#                 "email": credentials.email,
#                 "user_name": credentials.user_name,
#             },
#         }
#     )


# async def update_cache(agency: str, roles: list = []):
#     async_engine = get_async_engine()

#     if agency:
#         config_cache[agency] = await get_config(
#             agency=agency, controller=ConfigController(async_engine=async_engine)
#         )
#     if agency and roles:
#         await make_permissions_cache(
#             agency=agency,
#             roles=roles,
#             async_engine=async_engine,
#             refresh_permission_cache=True,
#         )