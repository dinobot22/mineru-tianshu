"""
PaddleOCR-VL 输出规范化器
"""

from pathlib import Path
from typing import Dict, Any
from loguru import logger
import shutil
import re
import json
from .base_output_normalizer import BaseOutputNormalizer


class PaddleOCROutputNormalizer(BaseOutputNormalizer):
    """
    PaddleOCR-VL 输出规范化器

    处理步骤：
    1. 为每页的图片添加页码前缀（page1_xxx.jpg），避免多页图片名称冲突
    2. 合并所有页的 JSON，并为 image 块添加 img_path 字段
    3. 更新 Markdown 中的图片引用路径
    """

    def _normalize_local_files(self, output_dir: Path) -> Dict[str, Any]:
        logger.info(f"🤖 Normalizing PaddleOCR-VL output: {output_dir}")

        # 1. 处理图片：重命名并移动到 images/ 目录
        standard_image_dir = output_dir / self.STANDARD_IMAGE_DIR
        standard_image_dir.mkdir(exist_ok=True)

        image_mapping = {}  # {page_idx: {原始名: 新名}}
        image_counter = 1  # 全局累进编号

        page_dirs = sorted(output_dir.glob("page_*"))

        for page_dir in page_dirs:
            # 提取页码（page_1 -> 1）
            try:
                page_num = int(page_dir.name.split("_")[1])
            except (IndexError, ValueError):
                logger.warning(f"⚠️  Invalid page directory: {page_dir.name}")
                continue

            # 查找该页的 imgs 目录
            imgs_dir = page_dir / "imgs"
            if not imgs_dir.exists():
                continue

            page_mapping = {}
            logger.info(f"📁 Processing {page_dir.name}/imgs/")

            # 处理该页的所有图片
            for img_file in imgs_dir.iterdir():
                if not img_file.is_file():
                    continue

                # 生成新文件名：image_001.jpg, image_002.jpg, ...
                file_ext = img_file.suffix
                new_name = f"image_{image_counter:03d}{file_ext}"
                new_path = standard_image_dir / new_name

                # 移动图片
                shutil.move(str(img_file), str(new_path))
                page_mapping[img_file.name] = new_name
                image_counter += 1
                logger.debug(f"   {img_file.name} -> {new_name}")

            image_mapping[page_num - 1] = page_mapping  # page_idx 从 0 开始

            # 删除空的 imgs 目录
            try:
                imgs_dir.rmdir()
            except OSError:
                pass

        logger.info(f"✅ Renamed {image_counter - 1} images with sequential numbering")

        # 2. 处理 JSON：合并所有页并添加 img_path 字段
        all_pages_data = []

        for page_dir in page_dirs:
            # 查找该页的 JSON 文件（格式：*_res.json）
            json_files = list(page_dir.glob("*_res.json"))

            if not json_files:
                logger.warning(f"⚠️  No JSON file in {page_dir.name}")
                continue

            json_file = json_files[0]

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    page_data = json.load(f)

                # 获取页码
                page_idx = page_data.get("page_index", 0)

                # 为图片块添加 img_path 字段
                if "parsing_res_list" in page_data:
                    page_img_mapping = image_mapping.get(page_idx, {})

                    for block in page_data["parsing_res_list"]:
                        if block.get("block_label") == "image":
                            # 根据 bbox 生成图片文件名（PaddleOCR 的命名规则）
                            bbox = block.get("block_bbox", [])
                            if len(bbox) == 4:
                                # 图片文件名格式：img_in_image_box_{x1}_{y1}_{x2}_{y2}.jpg
                                img_name = f"img_in_image_box_{bbox[0]}_{bbox[1]}_{bbox[2]}_{bbox[3]}.jpg"

                                # 查找对应的新文件名
                                if img_name in page_img_mapping:
                                    new_img_name = page_img_mapping[img_name]
                                    # 添加 img_path 字段（参考 MinerU 格式）
                                    block["img_path"] = f"{self.STANDARD_IMAGE_DIR}/{new_img_name}"
                                    logger.debug(f"   Added img_path: {block['img_path']}")

                all_pages_data.append(page_data)
                logger.info(f"✅ Processed {json_file.name}")

            except Exception as e:
                logger.warning(f"⚠️  Failed to process {json_file}: {e}")
                continue

        # 保存合并后的 JSON
        standard_json = None
        if all_pages_data:
            standard_json = output_dir / self.STANDARD_JSON_NAME
            combined_data = {
                "pages": all_pages_data,
                "total_pages": len(all_pages_data),
                "format": "paddleocr-vl",
            }

            with open(standard_json, "w", encoding="utf-8") as f:
                json.dump(combined_data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ Created {self.STANDARD_JSON_NAME} with {len(all_pages_data)} pages")

        # 3. 处理 Markdown：更新图片引用
        # 查找 result.md 文件
        md_files = list(output_dir.rglob("*.md"))
        standard_md = None

        if md_files:
            # 选择最大的 .md 文件（通常是主文件）
            main_md = max(md_files, key=lambda f: f.stat().st_size)

            # 如果不在根目录，移动到根目录
            standard_md = output_dir / self.STANDARD_MARKDOWN_NAME
            if main_md != standard_md:
                if main_md.parent != output_dir:
                    shutil.copy2(main_md, standard_md)
                else:
                    main_md.rename(standard_md)
                main_md = standard_md

            # 更新 Markdown 中的图片引用
            try:
                content = main_md.read_text(encoding="utf-8")

                # 构建完整的图片映射（所有页的图片）
                full_image_mapping = {}
                for page_mapping in image_mapping.values():
                    full_image_mapping.update(page_mapping)

                # 替换 Markdown 图片语法：![alt](path)
                md_img_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

                def replace_md_path(match):
                    alt_text = match.group(1)
                    img_path = match.group(2)
                    img_filename = Path(img_path).name

                    # 查找新文件名
                    if img_filename in full_image_mapping:
                        new_name = full_image_mapping[img_filename]
                        return f"![{alt_text}]({self.STANDARD_IMAGE_DIR}/{new_name})"
                    return match.group(0)

                # 替换 HTML img 标签：<img src="path" ...>
                html_img_pattern = r'<img\s+([^>]*\s+)?src="([^"]+)"([^>]*)>'

                def replace_html_path(match):
                    before_src = match.group(1) or ""
                    img_path = match.group(2)
                    after_src = match.group(3) or ""
                    img_filename = Path(img_path).name

                    # 查找新文件名
                    if img_filename in full_image_mapping:
                        new_name = full_image_mapping[img_filename]
                        return f'<img {before_src}src="{self.STANDARD_IMAGE_DIR}/{new_name}"{after_src}>'
                    return match.group(0)

                # 执行替换
                new_content = re.sub(md_img_pattern, replace_md_path, content)
                new_content = re.sub(html_img_pattern, replace_html_path, new_content)

                if new_content != content:
                    main_md.write_text(new_content, encoding="utf-8")
                    logger.info(f"✅ Updated image references in {main_md.name}")

            except Exception as e:
                logger.warning(f"⚠️  Failed to update markdown image references: {e}")

        logger.info("✅ PaddleOCR-VL normalization complete")

        return {
            "markdown_file": standard_md,
            "json_file": standard_json,
            "image_dir": standard_image_dir,
            "image_count": image_counter - 1,
        }
