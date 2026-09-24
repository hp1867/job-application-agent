"""Ordered extraction with explicit review warnings; never verifies candidate facts."""
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MAX_XML_BYTES=8*1024*1024


def docx_body(xml):
    if len(xml)>MAX_XML_BYTES:raise ValueError('DOCX body exceeds safe extraction size')
    if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():raise ValueError('XML entities are not supported')
    root=ET.fromstring(xml);body=root.find(W+'body')
    if body is None:raise ValueError('DOCX body is missing')
    segments=[];warnings=[]
    if next(root.iter(W+'txbxContent'),None) is not None:warnings.append('Text boxes need manual reading-order review')
    if next(root.iter(W+'ins'),None) is not None or next(root.iter(W+'del'),None) is not None:warnings.append('Tracked revisions need manual review')
    def walk(parent,path):
        for index,child in enumerate(parent):
            current=f'{path}/{child.tag.split("}")[-1]}[{index}]'
            if child.tag==W+'p':
                text=''.join(node.text or '' if node.tag==W+'t' else '\t' if node.tag==W+'tab' else '\n'
                    for node in child.iter() if node.tag in {W+'t',W+'tab',W+'br',W+'cr'})
                segments.append({'kind':'paragraph','source_path':current,'text':text})
            elif child.tag in {W+'tbl',W+'tr',W+'tc',W+'sdt',W+'sdtContent'}:walk(child,current)
    walk(body,'body')
    return {'text':'\n'.join(x['text'] for x in segments),'segments':segments,'warnings':warnings,
            'reading_order':'OOXML body order; table cells traversed row by row','visual_review':'PENDING'}


def extract_docx(path):
    with ZipFile(path) as archive:
        info=archive.getinfo('word/document.xml')
        if info.file_size>MAX_XML_BYTES:raise ValueError('DOCX body exceeds safe extraction size')
        result=docx_body(archive.read(info))
        if any(name.startswith(('word/header','word/footer')) and name.endswith('.xml') for name in archive.namelist()):
            result['warnings'].append('Header/footer content is excluded; review it for contact details')
        result['warnings'].append('Columns, drawings and page layout require visual review; extracted order is not layout approval')
        return result


def extract_pdf(path):
    from pypdf import PdfReader
    reader=PdfReader(path)
    if reader.is_encrypted:raise ValueError('Encrypted resume needs an unlocked user-supplied copy')
    if len(reader.pages)>50:raise ValueError('Resume exceeds the 50-page extraction bound')
    segments=[];warnings=[]
    for number,page in enumerate(reader.pages,1):
        text=page.extract_text() or ''
        segments.append({'kind':'page','page':number,'text':text})
        if not text.strip():warnings.append(f'Page {number} has no extractable text; OCR or manual review required')
    warnings.append('PDF content-stream order may differ from visual columns; inspect every page')
    return {'text':'\n\n'.join(x['text'] for x in segments),'segments':segments,'warnings':warnings,
            'reading_order':'PDF text extraction in page order','visual_review':'PENDING'}
