import re
import subprocess
import os
import glob
import logging
import shutil
import hashlib

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_diagram_caption(mermaid_code):
    comment_title_match = re.search(r'%%\s*Title:\s*(.*)', mermaid_code)
    if comment_title_match:
        return comment_title_match.group(1).strip()
    
    title_match = re.search(r'title\s+(.*)', mermaid_code)
    if title_match:
        return title_match.group(1).strip()
    
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
        
        caption = extract_diagram_caption(mermaid_code)
        
        with open(temp_mmd_file, 'w') as f:
            f.write(mermaid_code)
        
        try:
            result = subprocess.run([
                mermaid_command,
                '-i', temp_mmd_file,
                '-o', image_filename,
                '-b', 'transparent',
                '-s', '2',
                '--pdfFit', 'true'
            ], check=True, capture_output=True, text=True)
            logging.debug(f"Mermaid conversion output: {result.stdout}")
            
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

def process_markdown_files():
    markdown_files = glob.glob('*.md')
    
    sorted_files = sorted(markdown_files, key=lambda x: int(x.split('.')[0]) if x.split('.')[0].isdigit() else float('inf'))
    
    if "References.md" in sorted_files:
        sorted_files.remove("References.md")
        sorted_files.append("References.md")
    
    processed_files = []
    
    for file in sorted_files:
        logging.info(f"Processing file: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = convert_mermaid_to_images(content, file)
        
        temp_file = f'temp_{file}'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        processed_files.append(temp_file)
    
    return processed_files

def main():
    processed_files = process_markdown_files()
    
    pdf_options = [
        '--toc',
        '--toc-depth=2',
        '--number-sections',
        '--metadata', 'title="My Embedded Systems Book"',
        '--pdf-engine=xelatex',
        '--variable', 'documentclass=report',
        '--variable', 'papersize=a4paper',
        '--variable', 'geometry=margin=2.5cm',
        '--variable', 'classoption=oneside',
        '--variable', 'fontsize=11pt',
        '--variable', 'linkcolor=blue',
        '--variable', 'urlcolor=blue',
        # Remove the toccolor variable to keep the TOC black
        '--dpi=300',
        '--from', 'markdown+lists_without_preceding_blankline',
    ]
    
    if os.path.exists('references.bib'):
        pdf_options.extend(['--citeproc', '--bibliography=references.bib'])
    else:
        logging.warning("references.bib not found. Citations may not be processed correctly.")

    pdf_command = ['pandoc', '-o', 'output.pdf'] + pdf_options + processed_files
    run_pandoc(pdf_command)
    
    # Clean up temporary files
    for file in processed_files:
        os.remove(file)
    for file in glob.glob('mermaid_diagram_*.png'):
        os.remove(file)

def run_pandoc(command):
    logging.info(f"Running Pandoc command: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        logging.debug(f"Pandoc output: {result.stdout}")
        logging.info("PDF file created successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Pandoc error: {e.stderr}")
    except FileNotFoundError:
        logging.error("Pandoc not found. Please ensure Pandoc is installed and in your system PATH.")

if __name__ == '__main__':
    main()
