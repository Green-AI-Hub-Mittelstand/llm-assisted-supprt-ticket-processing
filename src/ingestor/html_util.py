from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from unstructured.partition.html import partition_html
from typing import List


def stringify_list(cl:List[str]) -> str:
    "\n".join(cl)


def elements_to_text(html_elements: List) -> str:
    """
    Convert a list of HTML elements into a formatted text string.

    Args:
        html_elements (List): A list of HTML elements represented as dictionaries
                            containing 'type' and 'text' keys, with an optional
                            'metadata' key for additional information like title depth.
    
    Returns:
        str: The formatted text string representation of the HTML elements.
    """
    text = []
    in_list = False  # Track if we're currently processing list items
    current_list = []  # List to collect consecutive list items

    for el in html_elements:
        el_dict = el.to_dict()  # Convert the element to a dictionary
        if el_dict["type"] == "Title":
            in_list = False  # Reset list tracking
            # Append accumulated list items before processing the title
            if current_list:
                text.append("\n".join(current_list))
                current_list.clear()
            # Create markdown-style heading based on category depth
            marker = "#" * (el_dict["metadata"]["category_depth"] + 1) + " "
            text.append(f"{marker}{el_dict['text']}")
        elif el_dict["type"] == "NarrativeText":
            in_list = False  # Reset list tracking
            # Append accumulated list items before processing the narrative text
            if current_list:
                text.append("\n".join(current_list))
                current_list.clear()
            # Append the narrative text to the main text list
            text.append(el_dict['text'])
        elif el_dict["type"] == "ListItem":
            in_list = True  # Mark that we are processing a list item
            # Append the formatted list item to the current list collection
            current_list.append(f"- {el_dict['text']}")

        else:
            in_list = False  # Reset list tracking for unknown types
            # Append accumulated list items before processing other elements
            if current_list:
                text.append("\n".join(current_list))
                current_list.clear()
            # Append the element's text to the main text list
            text.append(el_dict['text'])

    # Final check to append any remaining list items after loop completion
    if current_list:
        text.append("\n".join(current_list))

    # Join all parts into a single string with newline separation and strip whitespace
    return "\n".join(text).strip()


def process_html(url: str) -> str:
    """
    Scrape the HTML content from a dynamically generated website using Selenium,
    partition it, and convert it to a formatted text string.

    Args:
        url (str): The URL of the webpage to scrape.
    
    Returns:
        str: The formatted text string representation of the scraped HTML content.
             Returns None if no content is found or an error occurs.
    """
    # setup selenium for scraping dynamically generated websites
    options = webdriver.FirefoxOptions()

    options.add_argument('--headless')  # Run browser in headless mode
    # Recommended for running in headless environments
    options.add_argument('--no-sandbox')
    # Overcomes limited resource problems
    options.add_argument('--disable-dev-shm-usage')
    service = Service('/usr/local/bin/geckodriver')
    # Initialize the WebDriver
    driver = webdriver.Firefox(options=options, service=service)
    innercontent = None

    try:
        # Navigate to the URL
        driver.get(url)

        # Wait for the content to load
        wait = WebDriverWait(driver, 15)
        content = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'document-wapper-container')))

        # Extract and print the content
        if content:
            # print(content.text)
            innercontent = content.get_attribute("innerHTML")

        else:
            print("Content section not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the WebDriver
        driver.quit()
    
    if innercontent:
        # partition html
        html_el = partition_html(
            text=innercontent,
            skip_headers_and_footers=True)
        
        # Convert elements to formatted text
        return elements_to_text(html_el)

    return None  # Return None if no content is found or an error occurs
