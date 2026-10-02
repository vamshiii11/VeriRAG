import os, shutil
from pathlib import Path
from .config import resolve_backend_path, settings

class Storage:
    def __init__(self):
        self.provider=settings.storage_provider
        self.root=resolve_backend_path(settings.storage_path); self.root.mkdir(parents=True,exist_ok=True)
    def save(self,key:str,data:bytes):
        if self.provider=="s3":
            import boto3
            s3=boto3.client("s3",endpoint_url=settings.s3_endpoint or None,aws_access_key_id=settings.s3_access_key or None,aws_secret_access_key=settings.s3_secret_key or None,region_name=settings.s3_region or None)
            s3.put_object(Bucket=settings.s3_bucket,Key=key,Body=data)
        else:
            p=self.root/key; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data)
        return key
    def load(self,key:str):
        if self.provider=="s3":
            import boto3
            response=boto3.client("s3",endpoint_url=settings.s3_endpoint or None,aws_access_key_id=settings.s3_access_key or None,aws_secret_access_key=settings.s3_secret_key or None,region_name=settings.s3_region or None).get_object(Bucket=settings.s3_bucket,Key=key)
            return response["Body"].read()
        return (self.root/key).read_bytes()
    def delete(self,key:str):
        if self.provider=="s3":
            import boto3
            boto3.client("s3",endpoint_url=settings.s3_endpoint or None,aws_access_key_id=settings.s3_access_key or None,aws_secret_access_key=settings.s3_secret_key or None,region_name=settings.s3_region or None).delete_object(Bucket=settings.s3_bucket,Key=key)
        else:
            p=self.root/key
            if p.exists(): p.unlink()
storage=Storage()
