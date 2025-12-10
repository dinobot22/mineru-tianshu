"""
PDF 处理工具函数
"""

from pathlib import Path
from typing import List, Optional, Dict
from loguru import logger


def convert_pdf_to_images(pdf_path: Path, output_dir: Path, zoom: float = 2.0, dpi: Optional[int] = None) -> List[Path]:
    """
    将 PDF 所有页转换为图片

    这是一个公用的工具函数，被 PaddleOCR-VL 等引擎共同使用。

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
        zoom: 缩放比例（默认 2.0，即 2 倍）
        dpi: DPI 设置（可选，如果设置则会覆盖 zoom）

    Returns:
        转换后的图片路径列表

    Raises:
        RuntimeError: 如果 PyMuPDF 未安装或转换失败

    Example:
        >>> # 转换所有页
        >>> images = convert_pdf_to_images(
        ...     Path('document.pdf'),
        ...     Path('output/')
        ... )

        >>> # 自定义 DPI
        >>> images = convert_pdf_to_images(
        ...     Path('document.pdf'),
        ...     Path('output/'),
        ...     dpi=300
        ... )
    """
    try:
        import fitz  # PyMuPDF

        # 打开 PDF
        doc = fitz.open(str(pdf_path))

        # 获取页数
        page_count = len(doc)

        logger.info(f"📄 PDF has {page_count} pages")

        image_paths = []

        # 处理所有页面
        for page_num in range(page_count):
            page = doc[page_num]

            # 设置缩放/DPI
            if dpi:
                # 如果指定了 DPI，计算对应的缩放比例
                # 默认 PDF DPI 是 72
                zoom = dpi / 72.0

            mat = fitz.Matrix(zoom, zoom)

            # 渲染为图片
            pix = page.get_pixmap(matrix=mat)

            # 保存为 PNG（统一命名格式）
            image_path = output_dir / f"{pdf_path.stem}_page{page_num + 1}.png"

            pix.save(str(image_path))
            image_paths.append(image_path)

            logger.debug(f"   Converted page {page_num + 1}/{page_count} to PNG")

        # 关闭文档
        doc.close()

        logger.info(f"   Converted all {page_count} pages to PNG")

        return image_paths

    except ImportError:
        logger.error("❌ PyMuPDF not installed. Install with: pip install PyMuPDF")
        raise RuntimeError("PyMuPDF is required for PDF processing")
    except Exception as e:
        logger.error(f"❌ Failed to convert PDF to images: {e}")
        raise


def get_pdf_page_count(pdf_path: Path) -> int:
    """
    获取 PDF 页数

    Args:
        pdf_path: PDF 文件路径

    Returns:
        页数

    Raises:
        RuntimeError: 如果无法读取 PDF
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except ImportError:
        logger.error("❌ pypdf not installed. Install with: pip install pypdf")
        raise RuntimeError("pypdf is required for PDF processing")
    except Exception as e:
        logger.error(f"❌ Failed to read PDF: {e}")
        raise


def split_pdf_file(
    pdf_path: Path, output_dir: Path, chunk_size: int = 500, parent_task_id: str = None
) -> List[Dict[str, any]]:
    """
    拆分 PDF 文件为多个分片

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
        chunk_size: 每个分片的页数
        parent_task_id: 父任务ID (用于生成文件名)

    Returns:
        分片信息列表，每个元素包含:
        - path: 分片文件路径
        - start_page: 起始页码 (1-based)
        - end_page: 结束页码 (1-based)
        - page_count: 分片页数

    Example:
        >>> chunks = split_pdf_file(
        ...     Path('large.pdf'),
        ...     Path('output/'),
        ...     chunk_size=500
        ... )
        >>> # [
        >>> #   {'path': 'output/chunk_0_500.pdf', 'start_page': 1, 'end_page': 500, 'page_count': 500},
        >>> #   {'path': 'output/chunk_500_1000.pdf', 'start_page': 501, 'end_page': 1000, 'page_count': 500},
        >>> #   ...
        >>> # ]
    """
    try:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(pdf_path))
        total_pages = len(reader.pages)

        logger.info(f"✂️  Splitting PDF: {pdf_path.name} ({total_pages} pages)")
        logger.info(f"   Chunk size: {chunk_size} pages")

        chunks = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for i in range(0, total_pages, chunk_size):
            end_page = min(i + chunk_size, total_pages)
            chunk_page_count = end_page - i

            # 创建分片 PDF
            writer = PdfWriter()
            for page_num in range(i, end_page):
                writer.add_page(reader.pages[page_num])

            # 生成分片文件名
            if parent_task_id:
                chunk_filename = f"{parent_task_id}_chunk_{i+1}_{end_page}.pdf"
            else:
                chunk_filename = f"{pdf_path.stem}_chunk_{i+1}_{end_page}.pdf"

            chunk_path = output_dir / chunk_filename

            # 保存分片文件
            with open(chunk_path, "wb") as f:
                writer.write(f)

            chunk_info = {
                "path": str(chunk_path),
                "start_page": i + 1,  # 1-based
                "end_page": end_page,  # 1-based
                "page_count": chunk_page_count,
            }
            chunks.append(chunk_info)

            logger.info(f"   ✅ Created chunk {len(chunks)}: pages {i+1}-{end_page} ({chunk_page_count} pages)")

        logger.info(f"✅ Split into {len(chunks)} chunks")
        return chunks

    except ImportError:
        logger.error("❌ pypdf not installed. Install with: pip install pypdf")
        raise RuntimeError("pypdf is required for PDF splitting")
    except Exception as e:
        logger.error(f"❌ Failed to split PDF: {e}")
        raise


async def split_and_create_subtasks(
    parent_task_id: str,
    file_path: Path,
    chunk_size: int,
    backend: str,
    options: dict,
    priority: int,
    user_id: str,
    db,  # TaskDB instance
) -> List[str]:
    """
    拆分 PDF 并创建子任务

    Args:
        parent_task_id: 父任务ID
        file_path: PDF 文件路径
        chunk_size: 每个分片的页数
        backend: 处理后端
        options: 处理选项
        priority: 优先级
        user_id: 用户ID
        db: TaskDB 实例

    Returns:
        子任务ID列表
    """
    # 拆分 PDF
    upload_dir = file_path.parent
    chunks = split_pdf_file(file_path, upload_dir, chunk_size, parent_task_id)

    # 创建子任务
    child_task_ids = []
    total_pages = sum(chunk["page_count"] for chunk in chunks)

    for idx, chunk in enumerate(chunks):
        # 构建子任务选项（包含分片信息）
        child_options = {
            **options,
            "chunk_info": {
                "start_page": chunk["start_page"],
                "end_page": chunk["end_page"],
                "page_count": chunk["page_count"],
                "total_pages": total_pages,
                "chunk_index": idx,
                "total_chunks": len(chunks),
            },
        }

        # 创建子任务
        child_task_id = db.create_child_task(
            parent_task_id=parent_task_id,
            file_name=Path(chunk["path"]).name,
            file_path=chunk["path"],
            backend=backend,
            options=child_options,
            priority=priority,
            user_id=user_id,
        )

        child_task_ids.append(child_task_id)

    logger.info(f"📋 Created {len(child_task_ids)} subtasks for parent task {parent_task_id}")
    return child_task_ids
