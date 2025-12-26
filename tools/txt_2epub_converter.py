"""
将txt格式文本转换成epub电子书并且实现如下需求:
1. 支持自定义 epub 封面，字段 bookCover
2. 可以配置txt的读取规则, 如书名、作者字段
3. 可以配置txt内图片读取的规则，如正则表达式
4. 获取到txt内图片会尝试下载，如果是非.png等图片格式结尾的网址尝试魔数去读取是否是图片并进行转换
5. 自动根据章节生成epub相关的东西
6. txt文本目录可以自定义
7. 输出的epub目录也可以自定义
"""

import os
import re
import requests
import imghdr
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from ebooklib import epub
from PIL import Image
from io import BytesIO


class TxtToEpubConverter:
    def __init__(self, config: Dict):
        """
        初始化转换器
        config = {
            'input_dir': 'txtBooks_esjzone',  # txt输入目录
            'output_dir': 'epubBooks_esjzone',  # epub输出目录
            'book_cover': 'cover.jpg',  # 封面路径
            'title_pattern': r'^书名[：:]\s*(.+)$',  # 书名提取正则
            'author_pattern': r'^作者[：:]\s*(.+)$',  # 作者提取正则
            'chapter_pattern': r'^第[0-9零一二三四五六七八九十百千万]+[章节回]',  # 章节标题正则
            'image_pattern': r'https?://[^\s<>"{}|\\^`\[\]]+\.(?:jpg|jpeg|png|gif|webp)',  # 图片链接正则
            'headers': {'User-Agent': 'Mozilla/5.0'}  # 请求头
        }
        """
        self.input_dir = config.get('input_dir', 'txtBooks_esjzone')
        self.output_dir = config.get('output_dir', 'epubBooks_esjzone')
        self.book_cover = config.get('book_cover')
        self.title_pattern = config.get('title_pattern', r'^书名[：:]\s*(.+)$')
        self.author_pattern = config.get('author_pattern', r'^作者[：:]\s*(.+)$')
        self.chapter_pattern = config.get('chapter_pattern', r'^第[0-9零一二三四五六七八九十百千万]+[章节回]')
        self.image_pattern = config.get('image_pattern', r'https?://[^\s<>"{}|\\^`\[\]]+')
        self.headers = config.get('headers', {'User-Agent': 'Mozilla/5.0'})
        
        os.makedirs(self.output_dir, exist_ok=True)

    def download_image(self, url: str, is_cover: bool = False) -> Optional[Tuple[bytes, str]]:
        """
        下载图片并识别格式
        返回: (图片二进制数据, 扩展名) 或 None
        """
        try:
            prefix = "🎨" if is_cover else "  ⬇️ "
            print(f"{prefix} 下载图片: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            img_data = response.content
            
            # 使用魔数识别图片类型
            img_type = imghdr.what(None, h=img_data)
            if img_type:
                print(f"  ✓ 识别图片格式: {img_type} ({len(img_data)} bytes)")
                return img_data, img_type
            
            # 尝试用PIL打开并转换
            try:
                print(f"  🔄 使用PIL识别图片格式...")
                img = Image.open(BytesIO(img_data))
                output = BytesIO()
                img_format = img.format.lower() if img.format else 'jpeg'
                img.save(output, format=img_format)
                print(f"  ✓ 转换图片格式: {img_format} ({len(output.getvalue())} bytes)")
                return output.getvalue(), img_format
            except:
                print(f"  ✗ 无法识别图片格式")
                return None
        except Exception as e:
            print(f"  ✗ 下载图片失败 {url[:60]}...: {e}")
            return None

    def load_cover_image(self, cover_source: str) -> Optional[Tuple[bytes, str]]:
        """
        加载封面图片，支持本地路径和URL
        返回: (图片二进制数据, 扩展名) 或 None
        """
        if not cover_source:
            return None
        
        # 判断是URL还是本地路径
        if cover_source.startswith('http://') or cover_source.startswith('https://'):
            print(f"🎨 封面来源: 网络链接")
            return self.download_image(cover_source, is_cover=True)
        else:
            # 本地文件
            print(f"🎨 封面来源: 本地文件")
            if os.path.exists(cover_source):
                try:
                    print(f"  📂 读取本地封面: {cover_source}")
                    with open(cover_source, 'rb') as f:
                        img_data = f.read()
                    
                    # 识别格式
                    img_type = imghdr.what(None, h=img_data)
                    if not img_type:
                        # 尝试从文件扩展名获取
                        ext = Path(cover_source).suffix.lstrip('.')
                        img_type = ext if ext else 'jpeg'
                    
                    print(f"  ✓ 封面加载成功: {img_type} ({len(img_data)} bytes)")
                    return img_data, img_type
                except Exception as e:
                    print(f"  ✗ 读取本地封面失败: {e}")
                    return None
            else:
                print(f"  ✗ 本地封面文件不存在: {cover_source}")
                return None

    def parse_txt(self, txt_path: str) -> Dict:
        """
        解析txt文件，提取书名、作者、章节和内容
        """
        print(f"📖 读取文件: {txt_path}")
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        print(f"📄 文件总行数: {len(lines)}")
        
        book_info = {
            'title': Path(txt_path).stem,
            'author': '未知作者',
            'chapters': []
        }
        
        # 提取书名和作者
        print(f"🔍 解析元数据...")
        for line in lines[:50]:  # 只在前50行查找
            if not book_info.get('title_found'):
                title_match = re.match(self.title_pattern, line.strip())
                if title_match:
                    book_info['title'] = title_match.group(1)
                    book_info['title_found'] = True
                    print(f"  ✓ 书名: {book_info['title']}")
            
            author_match = re.match(self.author_pattern, line.strip())
            if author_match:
                book_info['author'] = author_match.group(1)
                print(f"  ✓ 作者: {book_info['author']}")
        
        # 分割章节
        print(f"📑 解析章节...")
        current_chapter = None
        current_content = []
        
        for line in lines:
            chapter_match = re.match(self.chapter_pattern, line.strip())
            if chapter_match:
                # 保存上一章节
                if current_chapter:
                    book_info['chapters'].append({
                        'title': current_chapter,
                        'content': '\n'.join(current_content)
                    })
                    print(f"  ✓ 章节 {len(book_info['chapters'])}: {current_chapter}")
                current_chapter = line.strip()
                current_content = []
            elif current_chapter:
                current_content.append(line)
        
        # 保存最后一章
        if current_chapter:
            book_info['chapters'].append({
                'title': current_chapter,
                'content': '\n'.join(current_content)
            })
            print(f"  ✓ 章节 {len(book_info['chapters'])}: {current_chapter}")
        
        print(f"📚 共解析 {len(book_info['chapters'])} 个章节")
        return book_info

    def process_images_in_content(self, content: str, book: epub.EpubBook, chapter_id: str) -> str:
        """
        处理内容中的图片链接，下载并添加到epub中
        """
        image_urls = re.findall(self.image_pattern, content)
        
        if image_urls:
            print(f"  🖼️  发现 {len(image_urls)} 张图片")
        
        for idx, url in enumerate(image_urls):
            result = self.download_image(url)
            if result:
                img_data, img_type = result
                img_name = f'{chapter_id}_img_{idx}.{img_type}'
                
                # 添加图片到epub
                epub_img = epub.EpubItem(
                    uid=f'img_{chapter_id}_{idx}',
                    file_name=f'images/{img_name}',
                    media_type=f'image/{img_type}',
                    content=img_data
                )
                book.add_item(epub_img)
                print(f"  ✓ 添加图片到EPUB: {img_name}")
                
                # 替换文本中的链接为img标签
                img_tag = f'<img src="images/{img_name}" alt="image" />'
                content = content.replace(url, img_tag)
        
        return content

    def create_epub(self, book_info: Dict, output_path: str):
        """
        创建epub电子书
        """
        print(f"\n📦 创建EPUB电子书...")
        book = epub.EpubBook()
        
        # 设置元数据
        print(f"⚙️  设置元数据...")
        book.set_identifier(book_info['title'])
        book.set_title(book_info['title'])
        book.set_language('zh-CN')
        book.add_author(book_info['author'])
        print(f"  ✓ 书名: {book_info['title']}")
        print(f"  ✓ 作者: {book_info['author']}")
        
        # 添加封面
        if self.book_cover:
            print(f"\n🎨 处理封面图片...")
            cover_result = self.load_cover_image(self.book_cover)
            if cover_result:
                cover_data, cover_type = cover_result
                cover_filename = f'cover.{cover_type}'
                book.set_cover(cover_filename, cover_data)
                print(f"  ✓ 封面已添加到EPUB")
            else:
                print(f"  ⚠️  封面加载失败，将跳过封面")
        
        # 创建章节
        print(f"\n📝 生成章节内容...")
        chapters = []
        toc = []
        total_chapters = len(book_info['chapters'])
        
        for idx, chapter_data in enumerate(book_info['chapters'], 1):
            print(f"\n[{idx}/{total_chapters}] 处理章节: {chapter_data['title']}")
            chapter_id = f'chapter_{idx}'
            content = chapter_data['content']
            
            # 处理内容中的图片
            content = self.process_images_in_content(content, book, chapter_id)
            
            # 创建章节
            chapter = epub.EpubHtml(
                title=chapter_data['title'],
                file_name=f'{chapter_id}.xhtml',
                lang='zh-CN'
            )
            chapter.content = f'<h1>{chapter_data["title"]}</h1><div>{content.replace(chr(10), "<br/>")}</div>'
            
            book.add_item(chapter)
            chapters.append(chapter)
            toc.append(chapter)
            
            # 统计章节字数
            content_length = len(chapter_data['content'])
            print(f"  ✓ 章节已生成 (文本长度: {content_length:,} 字符)")
        
        # 设置目录
        print(f"\n📋 生成目录结构...")
        book.toc = toc
        
        # 添加导航文件
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # 定义spine
        book.spine = ['nav'] + chapters
        print(f"  ✓ 目录结构已生成")
        
        # 写入epub文件
        print(f"\n💾 写入EPUB文件: {output_path}")
        epub.write_epub(output_path, book)
        print(f"✅ EPUB生成成功!\n")

    def convert(self, txt_filename: str):
        """
        转换单个txt文件为epub
        """
        txt_path = os.path.join(self.input_dir, txt_filename)
        if not os.path.exists(txt_path):
            print(f'❌ 文件不存在: {txt_path}')
            return
        
        print(f'\n{"="*60}')
        print(f'🚀 开始转换: {txt_filename}')
        print(f'{"="*60}\n')
        
        book_info = self.parse_txt(txt_path)
        
        output_filename = f"{book_info['title']}.epub"
        output_path = os.path.join(self.output_dir, output_filename)
        
        self.create_epub(book_info, output_path)
        
        print(f'{"="*60}')
        print(f'✅ 转换完成: {output_filename}')
        print(f'{"="*60}\n')

    def convert_all(self):
        """
        转换目录下所有txt文件
        """
        if not os.path.exists(self.input_dir):
            print(f'❌ 输入目录不存在: {self.input_dir}')
            return
        
        txt_files = [f for f in os.listdir(self.input_dir) if f.endswith('.txt')]
        
        if not txt_files:
            print(f'⚠️  目录中没有找到txt文件: {self.input_dir}')
            return
        
        print(f'\n{"#"*60}')
        print(f'📚 批量转换模式')
        print(f'📂 输入目录: {self.input_dir}')
        print(f'📁 输出目录: {self.output_dir}')
        print(f'📄 找到 {len(txt_files)} 个txt文件')
        print(f'{"#"*60}\n')
        
        success_count = 0
        fail_count = 0
        
        for idx, txt_file in enumerate(txt_files, 1):
            try:
                print(f'\n【{idx}/{len(txt_files)}】')
                self.convert(txt_file)
                success_count += 1
            except Exception as e:
                fail_count += 1
                print(f'\n{"="*60}')
                print(f'❌ 转换失败: {txt_file}')
                print(f'错误信息: {e}')
                print(f'{"="*60}\n')
        
        print(f'\n{"#"*60}')
        print(f'🎉 批量转换完成!')
        print(f'✅ 成功: {success_count} 个')
        if fail_count > 0:
            print(f'❌ 失败: {fail_count} 个')
        print(f'{"#"*60}\n')


if __name__ == '__main__':
    # 配置示例
    config = {
        'input_dir': '../txtBooks_esjzone',
        'output_dir': '../epubBooks_esjzone',
        # 可选：指定封面 (支持本地路径或URL)
        # 本地示例: 'cover.jpg'
        # URL示例: 'https://example.com/cover.jpg'
        'book_cover': 'https://images.novelpia.com/imagebox/cover/111c7dae064a289f0c96f4416e7a8c0c_379362_ori.file',
        'title_pattern': r'^书名[：:]\s*(.+)$',
        'author_pattern': r'^作者[：:]\s*(.+)$',
        'chapter_pattern': r'^第[0-9零一二三四五六七八九十百千万]+[章节回]',
        'image_pattern': r'https?://[^\s<>"{}|\\^`\[\]]+\.(?:jpg|jpeg|png|gif|webp|bmp|file)',
        'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    }
    
    converter = TxtToEpubConverter(config)
    # converter.convert_all()  # 转换所有txt文件
    converter.convert('败北成瘾的M系魔法少女_20251226104405.txt')  # 转换单个文件