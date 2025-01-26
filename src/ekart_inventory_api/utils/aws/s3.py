from typing import Dict, Optional

from fastapi import HTTPException, UploadFile
from starlette_context import context

from .settings.config import settings


class S3:
    def __init__(
        self,
        s3_client,
        bucket: Optional[str] = None,
        prefix: Optional[str] = None,
    ):
        if (
            not hasattr(s3_client, "_service_model")
            or s3_client._service_model.service_name != "s3"
        ):
            raise ValueError("Provided client is not an S3 client.")

        self.s3_client = s3_client
        self.bucket = bucket or settings.S3_BUCKET
        self.s3_connection = context.get("config", {}).get("S3_connection", {})
        self.prefix = prefix or self.build_prefix()

    def build_prefix(
        self, tenant_id: Optional[str] = None, integration: Optional[str] = None
    ) -> str:
        tenant_id = tenant_id or self.s3_connection.get("tenant_id")
        integration = integration or self.s3_connection.get("integration")
        if tenant_id and integration:
            return f"{tenant_id}/{integration}/"
        raise HTTPException(
            status_code=400, detail="Please provide tenant id and integration"
        )

    @staticmethod
    def add_prefix(prefix: str, key: str) -> str:
        if not key.startswith(prefix):
            return f"{prefix}{key}"
        return key

    def update_key(self, key):
        if self.prefix:
            if not key.startswith(self.prefix):
                key = f"{self.prefix}{key}"
        return key

    async def upload(
        self, key: str, file: UploadFile, metadata: Optional[dict] = None
    ) -> bool:
        key = self.add_prefix(self.prefix, key)
        try:
            async with self.s3_client as s3:
                await s3.upload_fileobj(
                    file.file,
                    self.bucket,
                    key,
                    ExtraArgs={"Metadata": metadata} if metadata else None,
                )
            return True
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to upload file: {str(e)}"
            )

    async def delete(self, filename: str) -> Dict[str, str]:
        try:
            async with self.s3_client as s3:
                await s3.delete_object(Bucket=self.bucket, Key=filename)
            return {"message": "File deleted successfully"}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to delete file: {str(e)}"
            )

    async def key_exists(self, key: str) -> bool:
        key = self.add_prefix(self.prefix, key)
        try:
            async with self.s3_client as s3:
                results = await s3.list_objects_v2(Bucket=self.bucket, Prefix=key)
            if "Contents" in results:
                for obj in results["Contents"]:
                    if obj["Key"] == key:
                        return True
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to check file existence: {str(e)}"
            )
        return False

    async def generate_presigned_post(
        self, key: str, expiration: int = 3600
    ) -> Dict[str, str]:
        key = self.add_prefix(self.prefix, key)
        try:
            async with self.s3_client as s3:
                response = await s3.generate_presigned_post(
                    Bucket=self.bucket, Key=key, ExpiresIn=expiration
                )
            return response
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate presigned post URL: {str(e)}",
            )

    async def get_signed_url(self, key: str, expiration: int = 3600) -> str:
        key = self.add_prefix(self.prefix, key)
        try:
            async with self.s3_client as s3:
                url = await s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expiration,
                )
            return url
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to generate presigned URL: {str(e)}"
            )

    async def list_files(self, key: str) -> list:

        key = self.add_prefix(self.prefix, key)
        try:
            async with self.s3_client as s3:
                results = await s3.list_objects_v2(Bucket=self.bucket, Prefix=key)
            if "Contents" in results:
                return results["Contents"]

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to check files existence: {str(e)}"
            )
        return []

    async def get_metadata(self, key: str) -> list:
        key = self.update_key(key)
        async with self.s3_client as s3:
            response = await s3.head_object(Bucket=self.bucket, Key=key)
            return response.get("Metadata", {})

    async def get_file_obj(self, key):
        key = self.update_key(key)
        async with self.s3_client as s3:
            response = await s3.get_object(Bucket=self.bucket, Key=key)
            content = await response["Body"].read()
            return content.decode("utf-8")
