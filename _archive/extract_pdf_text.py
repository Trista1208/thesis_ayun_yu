#!/usr/bin/env python3
"""
Extract text from a PDF file and save it to a text file.
"""

import sys
from pathlib import Path
from pypdf import PdfReader

def extract_pdf_text(pdf_path, output_path=None):
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Optional path to save the extracted text. 
                     If None, saves to same directory as PDF with .txt extension
    """
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        return False
    
    if output_path is None:
        output_path = pdf_path.with_suffix('.txt')
    else:
        output_path = Path(output_path)
    
    try:
        print(f"Reading PDF: {pdf_path}")
        reader = PdfReader(pdf_path)
        
        total_pages = len(reader.pages)
        print(f"Total pages: {total_pages}")
        
        all_text = []
        for i, page in enumerate(reader.pages, 1):
            print(f"Extracting text from page {i}/{total_pages}...", end='\r')
            text = page.extract_text()
            all_text.append(f"\n--- Page {i} ---\n")
            all_text.append(text)
        
        print(f"\nWriting extracted text to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(''.join(all_text))
        
        print(f"Successfully extracted {len(''.join(all_text))} characters from {total_pages} pages")
        print(f"Text saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return False

if __name__ == "__main__":
    # Default to the PDF in the current directory
    pdf_file = "005bd16b-bceb-4149-8be3-87a2a60520e3.pdf"
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        output_file = None
    
    extract_pdf_text(pdf_file, output_file)

