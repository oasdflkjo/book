import re
import subprocess
import os
import glob
import shutil
import logging
import hashlib

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_diagram_caption(mermaid_code):
    # Try to find a title in a comment
    comment_title_match = re.search(r'%%\s*Title:\s*(.*)', mermaid_code)
    if comment_title_match:
        return comment_title_match.group(1).strip()
    
    # If no comment title, try to find a title in the Mermaid code
    title_match = re.search(r'title\s+(.*)', mermaid_code)
    if title_match:
        return title_match.group(1).strip()
    
    # If no title, try to extract meaningful information based on diagram type
    if 'flowchart' in mermaid_code.lower():
        return "Flowchart Diagram"
    elif 'sequenceDiagram' in mermaid_code:
        return "Sequence Diagram"
    elif 'classDiagram' in mermaid_code:
        return "Class Diagram"
    elif 'stateDiagram' in mermaid_code:
        return "State Diagram"
    elif 'gantt' in mermaid_code.lower():
        return "Gantt Chart"
    elif 'pie' in mermaid_code.lower():
        return "Pie Chart"
    
    # If no specific type is identified, use a generic caption
    return f"Diagram {hashlib.md5(mermaid_code.encode()).hexdigest()[:6]}"

def convert_mermaid_to_images(markdown_content, filename):
    mermaid_command = shutil.which('mmdc') or shutil.which('mermaid-cli')
    if not mermaid_command:
        logging.warning("Mermaid CLI not found. Skipping Mermaid diagram conversion.")
        return markdown_content
    
    logging.info(f"Using Mermaid command: {mermaid_command}")
    
    mermaid_pattern = re.compile(r'```mermaid(.*?)```', re.DOTALL)
    matches = list(mermaid_pattern.finditer(markdown_content))
    
    if not matches:
        logging.info(f"No Mermaid diagrams found in {filename}")
        return markdown_content
    
    logging.info(f"Found {len(matches)} Mermaid diagram(s) in {filename}")
    
    for i, match in enumerate(matches):
        mermaid_code = match.group(1)
        image_filename = os.path.abspath(f'mermaid_diagram_{filename}_{i}.png')
        temp_mmd_file = os.path.abspath(f'temp_{filename}_{i}.mmd')
        
        logging.debug(f"Mermaid code for diagram {i} in {filename}:\n{mermaid_code}")
        
        # Extract or generate caption
        caption = extract_diagram_caption(mermaid_code)
        
        # Save Mermaid code to a temporary file
        with open(temp_mmd_file, 'w') as f:
            f.write(mermaid_code)
        
        try:
            # Convert Mermaid to image with higher resolution
            logging.debug(f"Attempting to convert Mermaid diagram {i} in {filename}")
            result = subprocess.run([
                mermaid_command,
                '-i', temp_mmd_file,
                '-o', image_filename,
                '-b', 'transparent',
                '-s', '2',  # Scale factor for higher resolution
                '--pdfFit', 'true'  # Fit diagram to PDF page
            ], check=True, capture_output=True, text=True)
            logging.debug(f"Mermaid conversion output: {result.stdout}")
            
            # Replace Mermaid code with image reference in Markdown, including the caption
            markdown_content = markdown_content.replace(match.group(0), f'![{caption}]({image_filename})')
            logging.info(f"Successfully converted Mermaid diagram {i} in {filename}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to convert Mermaid diagram {i} in {filename}. Error: {e}")
            logging.error(f"Mermaid CLI output: {e.stdout}")
            logging.error(f"Mermaid CLI error output: {e.stderr}")
        finally:
            if os.path.exists(temp_mmd_file):
                os.remove(temp_mmd_file)
    
    return markdown_content


def extract_chapter_info(content):
    # Extract the first h1 (chapter title) and all h2 (subchapter titles)
    chapter_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    subchapter_matches = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)
    
    chapter_title = chapter_match.group(1) if chapter_match else "Untitled Chapter"
    subchapters = subchapter_matches if subchapter_matches else []
    
    return chapter_title, subchapters

def process_markdown_files():
    markdown_files = glob.glob('*.md')
    
    # Sort files based on the chapter number in the filename
    sorted_files = sorted(markdown_files, key=lambda x: int(x.split('.')[0]))
    
    processed_files = []
    
    for file in sorted_files:
        logging.info(f"Processing file: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        updated_content = convert_mermaid_to_images(content, file)
        
        temp_file = f'temp_{file}'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        processed_files.append(temp_file)
    
    return processed_files

def main():
    processed_files = process_markdown_files()
    
    # Common Pandoc options for both EPUB and PDF
    common_options = [
        '--toc',
        '--toc-depth=2',
        '--number-sections',
        '--top-level-division=chapter',
        '--metadata', 'title="My Embedded Systems Book"'
    ]
    
    # Convert to EPUB using Pandoc
    epub_command = ['pandoc', '-o', 'output.epub'] + common_options + processed_files
    run_pandoc(epub_command, "EPUB")

    # Check if references.bib exists
    bibliography_option = []
    if os.path.exists('references.bib'):
        bibliography_option = ['--citeproc', '--bibliography=references.bib']
    else:
        logging.warning("references.bib not found. Citations may not be processed correctly.")

    # Convert to PDF using Pandoc with modified options
    pdf_engines = ['xelatex', 'pdflatex']
    for engine in pdf_engines:
        pdf_command = [
            'pandoc',
            '-o', 'output.pdf',
            '--pdf-engine=' + engine,
            '--variable', 'papersize=a4paper',
            '--variable', 'geometry=margin=2.5cm',
            '--variable', 'classoption=oneside',  # Ensures consistent layout
            '--variable', 'pagestyle=plain',      # Removes running headers
            '--no-highlight',                     # Disables syntax highlighting
            '--dpi=300',                          # Sets a higher DPI for images
            '--from', 'markdown+lists_without_preceding_blankline',  # Improved list parsing
        ] + bibliography_option + common_options + processed_files
        if run_pandoc(pdf_command, "PDF"):
            break
    else:
        logging.error("PDF generation failed. No suitable PDF engine found.")
    
    # Clean up temporary files
    for file in processed_files:
        os.remove(file)
    for file in glob.glob('mermaid_diagram_*.png'):
        os.remove(file)

def run_pandoc(command, output_type):
    logging.info(f"Running Pandoc command for {output_type}: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logging.debug(f"Pandoc output: {result.stdout}")
        logging.info(f"{output_type} file created successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Pandoc error for {output_type}: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error(f"Pandoc not found. Please ensure Pandoc is installed and in your system PATH.")
        return False

if __name__ == '__main__':
    main()
