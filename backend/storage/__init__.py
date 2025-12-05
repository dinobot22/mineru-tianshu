"""
对象存储模块

提供统一的对象存储接口，支持 RustFS (S3 兼容)
"""

from .rustfs_client import RustFSClient

__all__ = ["RustFSClient"]
