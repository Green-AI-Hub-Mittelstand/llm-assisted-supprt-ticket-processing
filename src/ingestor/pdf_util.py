import fitz
import re
from typing import List, Tuple, Set
from langdetect import detect
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling_core.types.doc.document import DEFAULT_EXPORT_LABELS
from docling.datamodel.document import TextItem, TableItem, DocItemLabel, SectionHeaderItem
from docling_core.types.doc.document import GroupItem, GroupLabel, ListItem
import pandas as pd
from io import BytesIO

def extract_table_of_contents(doc: fitz.Document) -> List[Tuple[str, int, int]]:
    """
    Extracts the table of contents (TOC) from a given PDF document using PyMuPDF (fitz).
    
    This function attempts to retrieve the TOC directly from the document's structure if available; otherwise, it parses the text content of each page.
    
    Parameters:
        doc (fitz.Document): The PyMuPDF Document object representing the PDF file.
        
    Returns:
        List[Tuple[str, int, int]]: A list of tuples containing section titles, their corresponding page numbers, and font sizes if available. Each tuple is structured as (section_title, page_number, font_size).
    
    Notes:
        - The function first checks for a built-in TOC in the document.
        - If no built-in TOC is found, it extracts sections by searching for titles followed by numbers or dots on each page.
        - Font sizes are used to identify and order sections as they appear in the document. Sections with larger font sizes are considered higher in the hierarchy.
    """

    # First try to get the built-in TOC if it exists
    toc = doc.get_toc()
    if toc:
        return [(title, page_num, level) for level, title, page_num in toc]

    # TOC entry patterns
    toc_pattern = r'^(.*?\S)\s*\.{2,}\s*(\d+)$'
    font_size_set = set()
    table_of_contents = []
    # If no built-in TOC, try to extract it from the content
    # Corrected to use doc.page_count instead of hardcoding 20
    for page_num in range(doc.page_count):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        # Concatenate text in the span
                        line_text += span["text"]
                        match = re.match(toc_pattern, line_text.strip())
                        if match:
                            section_title = match.group(1).strip()
                            page_number = int(match.group(2))
                            table_of_contents.append(
                                [section_title, page_number, span["size"]])
                            font_size_set.add(span["size"])
    ebenen_dict = {item: i for i, item in enumerate(
        sorted(font_size_set, reverse=True), 1)}
    table_of_contents = [[title, page_num, ebenen_dict[size]]
                         for title, page_num, size in table_of_contents]
    return table_of_contents


def detect_irrelevant_pages(doc: fitz.Document) -> Set[int]:
    """
    Detects and marks irrelevant pages in a PDF document based on specific criteria.

    This function identifies pages that are likely to be non-content pages, such as title pages or sections dedicated to notices and acknowledgments. It uses both textual analysis and structural cues from the PDF content.
    
    Parameters:
        doc (fitz.Document): The PyMuPDF Document object representing the PDF file.
        
    Returns:
        Set[int]: A set of page numbers that are considered irrelevant, marked for removal.
    
    Notes:
        - Pages with few words or containing certain keywords related to copyright and acknowledgments are flagged as potential non-content pages.
        - The function also checks for the presence of a table of contents (TOC) and sections dedicated to notices, acknowledgments, or other resources. If such sections are found, the associated pages are marked as irrelevant.
        - Enhanced detection mechanisms include searching for indicators like "contents", "table of contents", chapter listings with page numbers, and typical TOC formatting.
    """
    pages_to_remove = set()

    in_toc_section = False
    consecutive_toc_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text().lower()
        lang = None
        try:
            lang = detect(text)
        except Exception as e:
            print("Error detecting language of text: ", e)
        if lang == "en":
            # Check for title page indicators
            if page_num == 0 and (
                # Usually title pages have few words
                len(text.split()) < 100 or
                bool(re.search(r'by|author|copyright|all rights reserved', text))
            ):
                pages_to_remove.add(page_num)

            if bool(re.search(r'notices|acknowledgments', text)) and page_num <= 10:
                pages_to_remove.add(page_num)

            # Enhanced TOC detection patterns
            toc_patterns = [
                r'contents',
                r'table of contents',
                # Chapter listings with page numbers
                r'chapter\s+\d+.*?\.{2,}.*?\d+',
                # Numbered entries with page numbers
                r'^\s*\d+\..*?\.{2,}.*?\d+',
                r'^\s*[ivx]+\.',                   # Roman numeral listings
                # Pure number-to-page references
                r'^\s*\d+\s*\.{2,}\s*\d+$'
            ]

            # Check for TOC indicators
            has_toc_indicators = any(bool(re.search(pattern, text, re.MULTILINE))
                                     for pattern in toc_patterns)

            # Check for typical TOC formatting
            page_number_pattern = r'.*?\.{2,}.*?\d+$'
            has_page_numbers = len(re.findall(
                page_number_pattern, text, re.MULTILINE)) > 2

            if (has_toc_indicators or (in_toc_section and has_page_numbers)) and page_num < 20:
                pages_to_remove.add(page_num)
                if not in_toc_section:
                    # if first page of toc add all preceding pages (as they are usually preamble and irrelevant)
                    pages_to_remove.update(range(0, page_num))
                in_toc_section = True
                consecutive_toc_count += 1
            else:
                consecutive_toc_count = 0
                if consecutive_toc_count == 0:
                    in_toc_section = False
        else:
            pages_to_remove.add(page_num)
    toc = extract_table_of_contents(doc)
    for i, item in enumerate(toc):
        if re.search(r'other resources|additional resources|acronyms|abbreviations|abstract|index|recycling|specifications', item[0]):
            pages_to_remove.add(item[1])
            for j in range(i+1, len(toc)):
                if not toc[j][-1] == item[-1] or toc[j][-1] > item[-1]:
                    pages_to_remove.add(toc[j][1])
            if i+1 == len(toc):
                page = item[1]
                pages_to_remove.update(range(page, len(doc)))

    return pages_to_remove


def stringify_list(current_list: List[str], elements: List[Tuple[str, int]], current_list_page: int) -> Tuple[List[str], List[Tuple[str, int]]]:
    """
    Converts a list of strings into a single string and appends it to another list along with its associated page number.

    This function joins the elements of `current_list` into a single string separated by newline characters. It then adds this string along with `current_list_page` as a tuple to `elements`. Finally, it clears `current_list`.

    Parameters:
        current_list (List[str]): A list of strings that need to be joined into a single string.
        elements (List[Tuple[str, int]]): A list of tuples where each tuple contains a string and its corresponding page number. The new element will be added to this list.
        current_list_page (int): The page number associated with the strings in `current_list`.

    Returns:
        Tuple[List[str], List[Tuple[str, int]]]: A tuple containing an empty list (since `current_list` is cleared) and the updated `elements` list.

    Notes:
        - This function assumes that `current_list` can be joined into a single meaningful string using newline characters.
        - The function modifies `elements` in place by appending the new tuple.
    """
    # Join the elements of current_list with newline characters
    current_list_joined = "\n".join(current_list)
    
    # Append the joined string and its page number to elements
    elements.append((current_list_joined, current_list_page))
    
    # Clear the current_list for further use
    current_list.clear()
    
    return current_list, elements


def get_fullpage_tables(result, pti: Set[int]) -> Set[int]:
    """
    Identifies full-page tables in a document and adds their page numbers to the provided set.

    This function iterates over all items in the document, specifically looking for TableItem instances. A table is considered full-page if it occupies more than 70% of the page height and more than 60% of the page width.

    Parameters:
        result (Document): The document object containing the items to be analyzed.
        pti (Set[int]): A set to which the page numbers of full-page tables will be added.

    Returns:
        Set[int]: The updated set of page numbers, including those of identified full-page tables.
    
    Notes:
        - The function assumes that the `result` object has a `document` attribute with a `pages` list, where each page has a `size` attribute providing width and height.
        - Only items labeled in `DEFAULT_EXPORT_LABELS` are considered, and pages already marked as irrelevant (in `pti`) are skipped.
    """
    
    # Get the dimensions of the first page to use for comparison
    if len(result.document.pages) > 0:
        page_dims = (result.document.pages[1].size.width,
                     result.document.pages[1].size.height)
    else:
        return pti

    # Iterate over all items in the document
    for item, level in result.document.iterate_items():
        # Skip items not in default export labels or already marked as irrelevant
        if item.label not in DEFAULT_EXPORT_LABELS or item.prov[0].page_no - 1 in pti:
            continue
        
        # Check if the item is a table and meets the full-page criteria
        if isinstance(item, TableItem):
            page_height_ratio = round(item.prov[0].bbox.height / page_dims[1], 2)
            page_width_ratio = round(item.prov[0].bbox.width / page_dims[0], 2)
            
            # Add to set if table occupies more than 70% of height and 60% of width
            if page_height_ratio >= 0.7 and page_width_ratio > 0.6:
                pti.add(item.prov[0].page_no - 1)

    return pti


def process_pdf(pdf: BytesIO, pages_to_ignore: List[int] = [], tables: bool = False, big_tables: bool = False) -> List[Tuple[str, int]]:
    """
    Process a PDF document and extract relevant text and table content.

    This function converts the PDF into structured elements such as titles, section headers, lists, and tables. It can optionally ignore certain pages based on user input or detected full-page tables. The extracted content is formatted in Markdown and returned along with its associated page numbers.

    Parameters:
        pdf (BytesIO): A BytesIO object containing the PDF data.
        pages_to_ignore (List[int]): A list of page numbers to be ignored during processing. Defaults to an empty list.
        tables (bool): If True, include table content in the output. Defaults to False.
        big_tables (bool): If True, do not automatically detect and ignore full-page tables. Defaults to False.

    Returns:
        List[Tuple[str, int]]: A list of tuples where each tuple contains a string of extracted content in Markdown format and its corresponding page number.

    Notes:
        - The function uses the `DocumentConverter` from the Camelot library with options for PDF processing.
        - Pages are ignored based on the provided `pages_to_ignore` list or detected full-page tables if `big_tables` is False.
        - List items are handled with nested indentation based on their nesting level.
        - Table items are converted to Markdown format and included in the output if the `tables` parameter is True.
    """
    
    # Initialize tracking variables for list processing
    list_nesting_level = 0  # Current list nesting level
    previous_level = 0      # Previous item's level
    in_list = False         # Whether we're currently processing list items
    current_list = []       # Accumulate list items
    current_list_page = None# Track the page number of the current list
    indent = 4              # Indentation level for nested lists

    # Set up pipeline options for PDF conversion
    pipeline_options = PdfPipelineOptions(do_table_structure=True)
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

    # Create a document source from the provided BytesIO object
    source = DocumentStream(name="anleitung.pdf", stream=pdf)

    # Initialize the document converter with the specified format options
    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    
    # Convert the PDF to structured elements
    result = doc_converter.convert(source=source)
    
    # Detect and ignore full-page tables unless `big_tables` is True
    if not big_tables:
        pages_to_ignore = get_fullpage_tables(result, set(pages_to_ignore))
    
    # Initialize a list to store the extracted content with page numbers
    elements = []
    
    # Iterate over each item in the converted document
    for item, level in result.document.iterate_items():
        # Adjust the nesting level if moving up the hierarchy
        if level < previous_level:
            level_difference = previous_level - level
            list_nesting_level = max(0, list_nesting_level - level_difference)

        # Update the previous level for the next iteration
        previous_level = level
        
        # If we exit a list group, finalize the current list and reset tracking variables
        if (len(elements) > 0
                    and not isinstance(item, (ListItem, GroupItem))
                and in_list):
                if current_list:
                    current_list, elements = stringify_list(
                        current_list, elements, current_list_page)
                    current_list_page = None
                in_list = False
        
        # Skip items that are not in the default export labels
        if item.label not in DEFAULT_EXPORT_LABELS:
            continue
        
        # Skip items on pages marked for ignoring
        if (item.prov[0].page_no - 1) not in pages_to_ignore:
            # Handle title text items
            if isinstance(item, TextItem) and item.label == DocItemLabel.TITLE:
                if current_list and in_list:
                    current_list, elements = stringify_list(
                        current_list, elements, current_list_page)
                    current_list_page = None
                in_list = False
                # Format title text with a single '#' character
                text = f"# {item.text}"
                elements.append((text, item.prov[0].page_no))
            
            # Handle section header items and text items labeled as section headers
            elif (isinstance(item, TextItem) and item.label == DocItemLabel.SECTION_HEADER) or isinstance(item, SectionHeaderItem):
                if current_list and in_list:
                    current_list, elements = stringify_list(
                        current_list, elements, current_list_page)
                    current_list_page = None
                in_list = False
                # Determine the marker based on the level of the section header
                marker = "#" * min(level, 6) + " "
                if len(marker) < 3:
                    marker = "## "
                text = f"{marker}{item.text}"
                elements.append((text, item.prov[0].page_no))
            
            # Handle group items for lists and ordered lists
            elif isinstance(item, GroupItem):
                if item.label in [GroupLabel.LIST, GroupLabel.ORDERED_LIST]:
                    list_nesting_level += 1
                    in_list = True
                    current_list_page = item.prov[0].page_no
                else:
                    elements.append((item.text, item.prov[0].page_no))
            
            # Handle list items
            elif isinstance(item, ListItem) and item.label == DocItemLabel.LIST_ITEM:
                in_list = True
                current_list_page = item.prov[0].page_no
                # Determine the indentation based on the nesting level
                list_indent = " " * (indent * (list_nesting_level - 1))
                marker = ""
                if item.enumerated:
                    marker = f"{item.marker} "
                else:
                    marker = "- "
                text = f"{list_indent}{marker}{item.text}".strip()
                current_list.append(text)
            
            # Handle other text items
            elif isinstance(item, TextItem):
                if current_list and in_list:
                    current_list, elements = stringify_list(
                        current_list, elements, current_list_page)
                    current_list_page = None
                in_list = False
                elements.append((item.text, item.prov[0].page_no))
            
            # Handle table items if `tables` is True
            elif isinstance(item, TableItem) and tables:
                if current_list and in_list:
                    current_list, elements = stringify_list(
                        current_list, elements, current_list_page)
                    current_list_page = None
                in_list = False
                # Convert the table to a DataFrame and then to Markdown format
                table_df: pd.DataFrame = item.export_to_dataframe()
                elements.append((table_df.to_markdown(), item.prov[0].page_no))
    
    # Finalize any remaining list items at the end of the document
    if current_list:
        elements.append(("".join(current_list), current_list_page))
    
    return elements
