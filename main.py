import requests
import re
import subprocess
from bs4 import BeautifulSoup, NavigableString, Tag
from pylatex import Document, Section, Subsection, Command, Package
from pylatex.utils import NoEscape

def convert_html_latex(element):

    # print(f"element: {element}")

    if isinstance(element, NavigableString):
        text = str(element)
        text = text.replace('&', r'\&') # Escapes raw '&' symbol - TBD generalized helper function 
        return text
    elif isinstance(element, Tag):

        # Convert HTML tags:
        if element.name == 'em': # <em>
            return r'\emph{' + ''.join(convert_html_latex(c) for c in element.contents) + '}'

        elif element.name == 'strong': # <strong>
            return r'\textbf{' + ''.join(convert_html_latex(c) for c in element.contents) + '}'

        elif element.name == 'a': # Hyperlinks: '<a href="...">text</a>
            href = element.get('href', '#') # Get the href URL, or '#' as fallback
            text = ''.join(convert_html_latex(c) for c in element.contents)
            return r'\href{' + href + '}{' + text + '}' # LaTeX: '\href{url}{text}'

        else:                   # Default behavior = recurse w/o special formatting
            return ''.join(convert_html_latex(c) for c in element.contents)

    return ''


def extract_toc(toc_div):
    """"""

    toc_items = []

    def walk_list(ul_tag, level=1):

        # Loop through only direct <li> children (not nested <li> from deeper <ul>)
        for li in ul_tag.find_all('li', recursive=False):
            a_tag = li.find('a') # Find the <a> tag inside each <li>

            if a_tag and a_tag.has_attr('href'):

                # Extract the anchor ID (e.g. 'href="#Lifework" -> 'Lifework') 
                anchor_id = a_tag['href'].lstrip('#')

                # Extract the tile and remove '#.' format
                title = re.sub(r'^\d+\.\s*', '', a_tag.get_text(strip=True))

                # Add to flat TOC list
                toc_items.append({
                    'id': anchor_id,
                    'title': title,
                    'level': level
                })

            # check for a nested <ul> inside this <li> and recurse deeper
            nested_ul = li.find('ul')
            if nested_ul:
                walk_list(nested_ul, level + 1)

    walk_list(toc_div.find('ul'))

    # print(f"toc_items: {toc_items}")

    return toc_items
    

def fetch_entry(url):
    """"""

    # Send an HTTP GET request to the URL
    response = requests.get(url)
    
    # Parse the HTML content using BeautifulSoup with the lxml parser
    soup = BeautifulSoup(response.content, 'lxml')

    # Article overview section
    overview_div = soup.find('div', id='aueditable')

    # Extract the title from the <h1> tag
    title_tag = overview_div.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else 'No title found'

    # Extract publication information (ie publication / revision dates) from <div id="pubinfo">
    pub_info_tag = overview_div.find('div', id='pubinfo')
    pub_info = pub_info_tag.get_text(strip=True) if pub_info_tag else 'No publication info found'

    # Extract TOC sections
    toc_div = soup.find('div', id='toc')
    toc = extract_toc(toc_div) if toc_div else []

    # Extract the overview paragraph
    preamble_div = overview_div.find('div', id='preamble')
    overview_paragraph = ''
    if preamble_div:
        p_tag = preamble_div.find('p')
        if p_tag:
            overview_paragraph = convert_html_latex(p_tag)
            overview_paragraph = re.sub(r'\s+', ' ', overview_paragraph).strip() # strip whitespace, linebreaks, tabs, etc


    section_contents = {}
    
    # Populate the section bodies for subsequent LaTeX document build
    for section in toc:
        if section['level'] == 1:
            section_header = soup.find('h2', id=section['id'])
            content_parts = []

            for sibling in section_header.find_next_siblings():

                if sibling.name and sibling.name.startswith('h2'):
                    break       # stop at next main section
                if sibling.name == 'p':
                    latex_paragraph = convert_html_latex(sibling)
                    latex_paragraph = re.sub(r'\s+', ' ', latex_paragraph).strip() # strip whitespace, linebreaks, tabs, etc

                    content_parts.append(latex_paragraph)
                    
            section_contents[section['id']] = '\n\n'.join(content_parts)

        # if section['level'] == 2:
        #     section_header = soup.find('h3', id=section['id'])

        #     print(f"Section Header: {section_header}")

        #     content_parts = []

        #     for sibling in section_header.find_next_siblings():
        #         print(f"Sibling: {sibling}")
            

    return {
        'title': title,
        'publication': pub_info,
        'toc': toc,
        'overview': overview_paragraph,
        'section_contents': section_contents
    }

def build_latex_doc(data, filename="bergson"):
    doc = Document()

    doc.preamble.append(Package('parskip')) # Adds /usepackage{parskip} for line breaks

    # Set title and suppress auto-date
    doc.preamble.append(Command('title', data['title']))
    doc.preamble.append(Command('date', '')) # No date
    doc.append(NoEscape(r'\maketitle'))      # "\maketitle" LaTeX command renders the above; NoEscape passes literally (not escaped, eg: \\maketitle)

    # Add publication info under title
    doc.append(NoEscape(r'\noindent '))
    doc.append(data['publication'])
    doc.append('\n\n')

    # Add TOC and page break
    doc.append(NoEscape(r'\tableofcontents'))
    doc.append(NoEscape(r'\newpage'))

    # Add overview section
    doc.append(NoEscape(r'\section*{Overview}'))
    doc.append(NoEscape(data['overview']))
    doc.append(NoEscape(r'\newpage'))

    # bib_seen = False
    
    # Loop over ToC sections and add them as LaTex sections
    # for index, item in enumerate(data['toc']):
    #     print(index, item)

    bib_id = None
    
    for index, item in enumerate(data['toc']):

        if item['id'].lower() == 'bib':
            bib_id = index

        if bib_id and item['level'] == 1:
            print(item)
            break

        if item['level'] == 1:

            section_id = item['id']
            section_text = data['section_contents'][section_id]
            
            doc.append(NoEscape(rf'\section{{{item["title"]}}}'))
            doc.append(NoEscape(section_text))

        elif item['level'] == 2:

            section_id = item['id']
            # section_text = data['section_contents'][section_id]

            doc.append(NoEscape(rf'\subsection{{{item["title"]}}}'))
            # doc.append(NoEscape(section_text))

        # if item['id'].lower() == 'bib':
        #     bib_id = index

    # Generate LaTeX file
    doc.generate_tex(filename)

def compile_pdf(tex_filename):
    subprocess.run(['pdflatex', tex_filename], check=True)
    
if __name__ == "__main__":
    # Define the SEP entry url for testing

    url = "https://plato.stanford.edu/entries/bergson/"

    # Fetch and parse the entry
    data = fetch_entry(url)

    # print("===== RAW Data: =====")
    # print(data)

    # print("RAW publication data:")
    # print(repr(data['publication'])) 

    # Print the extracted data in a readable format
    # print(data)

    build_latex_doc(data)
    
    compile_pdf("bergson.tex")
