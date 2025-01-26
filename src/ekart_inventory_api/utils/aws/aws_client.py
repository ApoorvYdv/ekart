from typing import AsyncGenerator

import aioboto3
from botocore.config import Config

from .settings.config import settings


class AWSServices:
    S3 = "s3"
    SNS = "sns"
    COGNITO = "cognito-idp"
    LAMBDA = "lambda"


async def get_client(service: AWSServices):
    """
    Creates and returns an async client for the specified AWS service.
    """
    session = aioboto3.Session()
    async with session.client(
        service,
        config=Config(signature_version="s3v4"),
        **{
            k: v
            for k, v in {
                "aws_access_key_id": settings.get("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": settings.get("AWS_SECRET_ACCESS_KEY"),
                "region_name": settings.get("AWS_REGION"),
            }.items()
            if v
        },
    ) as client:
        yield client


async def get_s3() -> AsyncGenerator:
    """
    Returns an asynchronous generator for the S3 client.
    """
    async for s3_client in get_client(AWSServices.S3):
        yield s3_client


async def get_sns() -> AsyncGenerator:
    """
    Returns an asynchronous generator for the SNS client.
    """
    async for sns_client in get_client(AWSServices.SNS):
        yield sns_client


async def get_cognito() -> AsyncGenerator:
    """
    Returns an asynchronous generator for the Cognito client.
    """
    async for cognito_client in get_client(AWSServices.COGNITO):
        yield cognito_client


async def get_lambda() -> AsyncGenerator:
    """
    Returns an asynchronous generator for the SNS client.
    """
    async for lambda_client in get_client(AWSServices.LAMBDA):
        yield lambda_client
