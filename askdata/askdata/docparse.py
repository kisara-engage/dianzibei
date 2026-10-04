"""文档解析：Markdown / 文本 / DOCX 直接读；PDF 走 pdfplumber（可选）。"""
import pathlib
import re
import zipfile


def read_markdown_or_text(path):
    return pathlib.Path(path).read_text(encoding='utf-8', errors='replace')


def read_docx(path):
    """不依赖 python-docx：直接解 zip 读 document.xml 段落文本。"""
    from xml.etree import ElementTree as ET
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    root = ET.fromstring(xml)
    lines = []
    for para in root.iter(ns + 'p'):
        text = ''.join(node.text or '' for node in para.iter(ns + 't'))
        if text.strip():
            lines.append(text.strip())
    return '\n\n'.join(lines)


def read_pdf(path):
    """PDF 需 pdfplumber 或 pypdf；未安装时明确报错，不静默失败。"""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return '\n\n'.join((page.extract_text() or '') for page in pdf.pages)
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return '\n\n'.join((page.extract_text() or '') for page in reader.pages)
    except ImportError:
        raise RuntimeError('解析 PDF 需要安装 pdfplumber 或 pypdf：pip install pdfplumber')


def extract_text(path):
    """按扩展名选择解析器，返回纯文本。"""
    path = pathlib.Path(path)
    suffix = path.suffix.lower()
    if suffix in ('.md', '.markdown', '.txt'):
        text = read_markdown_or_text(path)
    elif suffix == '.docx':
        text = read_docx(path)
    elif suffix == '.pdf':
        text = read_pdf(path)
    else:
        raise ValueError(f'暂不支持的文档格式: {suffix}')
    # 归一化空白，但保留段落分隔
    text = re.sub(r'[ \t\u3000]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def doc_title(text, fallback):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('#'):
            return line.lstrip('# ').strip()
        if line:
            return line[:40]
    return fallback


SUPPORTED = ('.md', '.markdown', '.txt', '.docx', '.pdf')
