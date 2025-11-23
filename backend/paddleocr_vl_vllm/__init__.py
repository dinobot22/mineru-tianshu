"""
PaddleOCR-VL 解析引擎
支持 100+ 语言的 OCR 和文档解析
"""

from .engine import PaddleOCRVLVLLMEngine, get_engine

__all__ = ["PaddleOCRVLVLLMEngine", "get_engine"]
