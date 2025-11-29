"""
MinerU Pipeline Engine
单例模式，每个进程只加载一次模型（实际上MinerU的模型初始化是由mineru.cli.common.do_parse的导入来进行触发的，这里作为引擎封装来统一引擎的加载格式）
使用 MinerU 处理 PDF 和图片
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from threading import Lock
from loguru import logger
import img2pdf


class MinerUPipelineEngine:
    """
    MinerU Pipeline 引擎

    特性：
    - 单例模式
    - 封装 MinerU 的 do_parse 调用
    - 延迟加载（避免过早初始化模型）
    - 支持 PDF 和图片（自动转换）
    - 自动处理输出路径和结果解析
    - 线程安全
    """

    _instance: Optional["MinerUPipelineEngine"] = None
    _lock = Lock()
    _pipeline = None  # 这里的 pipeline 实际上是 do_parse 函数
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, device: str = "cuda:0"):
        """
        初始化引擎

        Args:
            device: 设备 (cuda:0, cuda:1 等)
        """
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.device = device

            # 从 device 字符串中提取 GPU ID
            if "cuda:" in device:
                self.gpu_id = device.split(":")[-1]
            else:
                self.gpu_id = "0"

            self._initialized = True
            logger.info(f"🔧 MinerU Pipeline Engine initialized on {device}")

    def _load_pipeline(self):
        """延迟加载 MinerU 管道 (do_parse)"""
        if self._pipeline is not None:
            return self._pipeline

        with self._lock:
            if self._pipeline is not None:
                return self._pipeline

            logger.info("=" * 60)
            logger.info("📥 Loading MinerU Pipeline (do_parse)...")
            logger.info("=" * 60)

            try:
                # 延迟导入 do_parse，避免过早初始化模型
                from mineru.cli.common import do_parse

                self._pipeline = do_parse

                logger.info("=" * 60)
                logger.info("✅ MinerU Pipeline loaded successfully!")
                logger.info("=" * 60)

                return self._pipeline

            except ImportError:
                logger.error("❌ Failed to import mineru.cli.common.do_parse")
                raise
            except Exception as e:
                logger.error(f"❌ Error loading MinerU pipeline: {e}")
                raise

    def cleanup(self):
        """清理显存"""
        try:
            from mineru.utils.model_utils import clean_memory

            clean_memory()
            logger.debug("🧹 MinerU: Memory cleanup completed")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Memory cleanup warning: {e}")

    def parse(self, file_path: str, output_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        处理文件

        Args:
            file_path: 输入文件路径
            output_path: 输出目录路径
            options: 处理选项

        Returns:
            包含结果的字典
        """
        options = options or {}
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        file_stem = Path(file_path).stem
        file_ext = Path(file_path).suffix.lower()

        # 加载管道 (do_parse 函数)
        do_parse_func = self._load_pipeline()

        try:
            # 读取文件为字节
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            # MinerU 的 do_parse 只支持 PDF 格式
            # 图片文件需要先转换为 PDF
            if file_ext in [".png", ".jpg", ".jpeg"]:
                logger.info("🖼️  Converting image to PDF for MinerU processing...")
                try:
                    pdf_bytes = img2pdf.convert(file_bytes)
                    file_name = f"{file_stem}.pdf"  # 使用 .pdf 扩展名
                    logger.info(f"✅ Image converted: {file_name} ({len(pdf_bytes)} bytes)")
                except Exception as e:
                    logger.error(f"❌ Image conversion failed: {e}")
                    raise ValueError(f"Failed to convert image to PDF: {e}")
            else:
                # PDF 文件直接使用
                pdf_bytes = file_bytes
                file_name = Path(file_path).name

            # 获取语言设置
            # MinerU 不支持 "auto"，默认使用中文
            lang = options.get("lang", "auto")
            if lang == "auto":
                lang = "ch"
                logger.info("🌐 Language set to 'ch' (MinerU doesn't support 'auto')")

            # 调用 MinerU (do_parse)
            do_parse_func(
                pdf_file_names=[file_name],  # 文件名列表
                pdf_bytes_list=[pdf_bytes],  # 文件字节列表
                p_lang_list=[lang],  # 语言列表
                output_dir=str(output_dir),  # 输出目录
                output_format="md_json",  # 同时输出 Markdown 和 JSON
                end_page_id=options.get("end_page_id"),
                layout_mode=options.get("layout_mode", True),
                formula_enable=options.get("formula_enable", True),
                table_enable=options.get("table_enable", True),
            )

            # MinerU 新版输出结构: {output_dir}/{file_name}/auto/{file_stem}.md
            # 递归查找 markdown 文件和 JSON 文件
            md_files = list(output_dir.rglob("*.md"))

            if md_files:
                # 使用第一个找到的 md 文件
                md_file = md_files[0]
                logger.info(f"✅ Found MinerU output: {md_file}")
                content = md_file.read_text(encoding="utf-8")

                # 返回实际的输出目录（包含 auto/ 子目录）
                actual_output_dir = md_file.parent

                # 查找 JSON 文件
                # MinerU 输出的 JSON 文件格式: {filename}_content_list.json, {filename}_middle.json, {filename}_model.json
                # 我们主要关注 content_list.json（包含结构化内容）
                json_files = [
                    f
                    for f in actual_output_dir.rglob("*.json")
                    if "_content_list.json" in f.name and not f.parent.name.startswith("page_")
                ]

                result = {
                    "markdown": content,
                    "result_path": str(actual_output_dir),  # 返回包含所有输出的目录
                }

                # 如果找到 JSON 文件，也读取它
                if json_files:
                    json_file = json_files[0]
                    logger.info(f"✅ Found MinerU JSON output: {json_file}")
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            json_content = json.load(f)
                        result["json_path"] = str(json_file)
                        result["json_content"] = json_content
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to load JSON: {e}")
                else:
                    logger.info("ℹ️  No JSON output found (MinerU may not generate it by default)")

                return result
            else:
                # 如果找不到 md 文件，列出输出目录内容以便调试
                logger.error("❌ MinerU output directory structure:")
                for item in output_dir.rglob("*"):
                    logger.error(f"   {item}")
                raise FileNotFoundError(f"MinerU output not found in: {output_dir}")

        finally:
            self.cleanup()


# 全局单例
_engine = None


def get_engine() -> MinerUPipelineEngine:
    """获取全局引擎实例"""
    global _engine
    if _engine is None:
        _engine = MinerUPipelineEngine()
    return _engine
