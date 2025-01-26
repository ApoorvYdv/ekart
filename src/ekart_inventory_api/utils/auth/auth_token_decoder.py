from functools import lru_cache
from typing import Any, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import jwt
from pydantic import BaseModel
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED

from .core.controllers.dependencies import get_client_header
from .settings.config import settings
from .utils.aws.async_aws_client import get_cognito
from .utils.aws.aws_client import AWSServices, get_client
from .utils.common.logger import logger
from .utils.user.user import decode_user_access


class ArrayUserAttribute:
    """
    A wrapper class used to handle operations with
    AWS Cognito custom attributes that represent an array of strings
    """

    def __init__(self, attribute_string: str | None) -> None:
        """
        Converts the custom user attribute string into a Python  dictionary
        depending on the format and stores it as an object property.

        For user attributes (agency with scores):
        - `"COMP1:1;COMP2:2" -> {'COMP1': 1, 'COMP2': 2}`
        """

        if attribute_string is None:
            self.values: dict[str, str] = dict()
        elif ":" in attribute_string:
            self.values = {
                pair.split(":")[0]: pair.split(":")[1]
                for pair in attribute_string.split(";")
            }

    def reconstruct_string(self):
        if not self.values:
            return None
        elif isinstance(self.values, dict):
            if len(self.values) == 1:
                key, value = next(iter(self.values.items()))
                return f"{key}:{value}"
            else:
                return ";".join(f"{key}:{value}" for key, value in self.values.items())

    def __contains__(self, item):
        return item in self.values

    def add(self, item: dict):

        if isinstance(self.values, dict):
            if isinstance(item, dict):
                self.values.update(item)
            else:
                raise ValueError(
                    "item must be a dictionary when self.values is a dictionary."
                )

    def delete(self, item: str):

        if isinstance(self.values, dict):
            self.values.pop(item, None)

    def __repr__(self) -> str:
        return str(self.values)

    def __str__(self) -> str:
        return str(self.values)

    def __iter__(self):
        return iter(self.values)


class JWKS(BaseModel):
    keys: list[dict[str, str]]


class JWTAuthorizationCredentials(BaseModel):
    jwt_token: str
    header: dict[str, str]
    claims: dict[str, str | list[str] | int]
    signature: str
    message: str
    super_admin: str | None
    user_companies: dict[str, str]
    roles: list[str]
    first_name: str
    last_name: str
    email: str
    user_name: str

    class Config:
        arbitrary_types_allowed = True


@lru_cache(maxsize=5)
def get_jwks(user_pool_id: str) -> JWKS:
    endpoint = (
        f"https://cognito-idp.{user_pool_id.split('_')[0]}"
        f".amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    )
    response = httpx.get(endpoint)
    if response.status_code != 200:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Unable to fetch JWKS of default Cognito user pool",
        )
    jwks = JWKS.model_validate(response.json())
    return jwks


class JWTBearer(HTTPBearer):
    def __init__(self, jwks: JWKS, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
        self.jwks = jwks

    async def __call__(
        self,
        request: Request,
        agency: str = Depends(get_client_header),
        cognito_client=Depends(get_cognito),
    ):
        jwt_token = request.headers.get("Authorization")
        if jwt_token:
            try:
                jwt_token = jwt_token.split(" ")[1]
                message, signature = jwt_token.rsplit(".", 1)
                claims = jwt.decode(jwt_token, self.jwks.model_dump())

                user_attributes = await cognito_client.get_user(AccessToken=jwt_token)
                user_name = user_attributes["Username"]
                user_attributes_dict = {
                    attribute["Name"]: attribute["Value"]
                    for attribute in user_attributes["UserAttributes"]
                }
                first_name = user_attributes_dict.get("given_name", "")
                last_name = user_attributes_dict.get("family_name", "")
                email = user_attributes_dict.get("email", "")
                user_companies = ArrayUserAttribute(
                    user_attributes_dict.get("custom:custom_user")
                ).values
                roles = decode_user_access(user_companies.get(agency))

                super_admin = None

                if user_attributes_dict.get("custom:custom_superadmin"):
                    super_admin = user_attributes_dict.get("custom:custom_superadmin")

                jwt_credentials = JWTAuthorizationCredentials(
                    jwt_token=jwt_token,
                    header=jwt.get_unverified_header(jwt_token),
                    claims=claims,
                    signature=signature,
                    message=message,
                    user_companies=user_companies,
                    super_admin=super_admin,
                    roles=roles,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    user_name=user_name,
                )

            except Exception as ex:
                logger.error(ex)
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED, detail="Invalid JWT"
                )
            return jwt_credentials
        else:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED, detail="Not Authenticated"
            )


auth = JWTBearer(get_jwks(settings.COGNITO_USER_POOL_ID))


def super_admin_validator(credentials: JWTAuthorizationCredentials = Depends(auth)):
    if "QUICKET" == credentials.super_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operation not permitted")
    return credentials
