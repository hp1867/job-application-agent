import unittest
from unittest.mock import patch,Mock
from backend.app.services.document_extraction import docx_body,extract_pdf

def body(content):return ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+content+'</w:body></w:document>').encode()
def p(text):return '<w:p><w:r><w:t>'+text+'</w:t></w:r></w:p>'

class DocumentExtractionTests(unittest.TestCase):
    def test_paragraph_table_paragraph_order(self):
        xml=body(p('Education')+'<w:tbl><w:tr><w:tc>'+p('University')+'</w:tc></w:tr></w:tbl>'+p('Experience'))
        result=docx_body(xml)
        self.assertEqual(result['text'],'Education\nUniversity\nExperience')
        self.assertIn('/tbl[1]/tr[0]/tc[0]/p[0]',result['segments'][1]['source_path'])
    def test_hyperlink_and_run_order(self):
        xml=body('<w:p><w:hyperlink><w:r><w:t>LinkedIn</w:t></w:r></w:hyperlink><w:r><w:tab/><w:t>Profile</w:t><w:br/><w:t>Next</w:t></w:r></w:p>')
        self.assertEqual(docx_body(xml)['text'],'LinkedIn\tProfile\nNext')
    def test_entities_rejected(self):
        with self.assertRaises(ValueError):docx_body(b'<!DOCTYPE x [<!ENTITY e "bad">]>'+body(p('test')))
    def test_missing_body_rejected(self):
        with self.assertRaises(ValueError):docx_body(b'<document/>')
    def test_revisions_warn(self):
        result=docx_body(body(p('Test')+'<w:ins>'+p('Revision')+'</w:ins>'))
        self.assertTrue(any('revisions' in x for x in result['warnings']))
        self.assertEqual(result['visual_review'],'PENDING')
    def test_pdf_page_provenance_and_blank_page_warning(self):
        reader=Mock(is_encrypted=False,pages=[Mock(extract_text=lambda:'Page one'),Mock(extract_text=lambda:'')])
        with patch('pypdf.PdfReader',return_value=reader):result=extract_pdf('unused-synthetic-path')
        self.assertEqual(result['segments'][1]['page'],2)
        self.assertTrue(any('Page 2' in x for x in result['warnings']))
    def test_encrypted_pdf_refused(self):
        with patch('pypdf.PdfReader',return_value=Mock(is_encrypted=True)):
            with self.assertRaises(ValueError):extract_pdf('unused')
    def test_large_pdf_refused(self):
        with patch('pypdf.PdfReader',return_value=Mock(is_encrypted=False,pages=[None]*51)):
            with self.assertRaises(ValueError):extract_pdf('unused')
