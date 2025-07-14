from ingestor.utils import add_ticket_to_db, add_manual_chunks_to_db, determine_relevancy
from ingestor.pdf_util import process_pdf, detect_irrelevant_pages
from ingestor.html_util import process_html
from utils.utils_historic_tickets import process_description, summarize_historic_ticket
from utils.utils_download_manuals import download_manuals_hp_all
from utils.chunking import naive_chunking
from utils.utils_db import check_new_devices, check_new_tickets, check_deleted_devices, check_deleted_tickets, get_consumed_parts
import fitz
import requests
import io, os



def add_ticket(ticketid, description, worknote, deviceType, remoteFix, success):
    # preprocessing of description
    description = process_description(description)
    spare_parts = get_consumed_parts(ticketid)
    spare_parts = [str(part["partDescription"]) for part in spare_parts]
    try: 
        # summary worknote description
        summary = summarize_historic_ticket(description, 
                                            worknote, 
                                            success, 
                                            remoteFix,
                                            spare_parts=spare_parts,
                                            model="qwen2.5:3b"
                                            )
        # add to vectordb
        add_ticket_to_db(summary, deviceType, ticketID=ticketid)
    except Exception as e:
        print(f"Ticket {ticketid} could not be added to vector db")
        print("Error: ", e)

def add_manual(deviceType, deviceModel):
    """
    Downloads and processes manuals for a given device type and model.
    The function downloads relevant manuals, processes them (either PDF or HTML),
    chunks the content, and adds the chunks to a vector database.

    Parameters:
        deviceType (str): The type of the device for which manuals are being downloaded.
        deviceModel (str): The specific model number of the device.

    Returns:
        int: The count of documents that were successfully added to the database.
    """
    added_docs_count = 0
    alldocs, deviceModel_used = download_manuals_hp_all(product_number=deviceModel, product_name=deviceType)
    for doc in alldocs:
        if "url" in doc.keys():
            if determine_relevancy(doc):
                if "pdf" in doc["url"] or "fileBytes" in doc.keys():
                    response = requests.get(doc["url"])
                    if response.status_code == 200:
                        fitzdoc = fitz.open(stream=response.content)
                        # clean pdf
                        pages_to_ignore = detect_irrelevant_pages(fitzdoc)
                        fitzdoc.close()
                            # partition pdf
                        elements = process_pdf(pdf=io.BytesIO(response.content), pages_to_ignore=pages_to_ignore)
                        # chunk elements
                        chunks = naive_chunking(elements)
                        # add chunks to vectordb
                        add_manual_chunks_to_db(chunks, devicetype=deviceType, deviceModel_used=deviceModel_used, url=doc["url"])
                        added_docs_count += 1
                    else:
                        print(f"Failed to download PDF. Status code: {response.status_code}")
                else:
                    chunk = process_html(doc["url"])
                    chunk = [{"text": chunk, "page_no": None}]
                    add_manual_chunks_to_db(chunks=chunk, devicetype=deviceType, deviceModel_used=deviceModel_used, doc_type="html", url=doc["url"])
                    added_docs_count += 1

def sync_tickets():
    # check for new finished tickets in production db
    # execute add_ticket function for each new ticket
    pass

def sync_devices():
    # check for new devicemodels and devicetypes by comparing production db and vectordb (unique devictypes)
    # execute add_manual function for each new devicetype
    pass

def main():
    sync_tickets()
    sync_devices()

if __name__ == "__main__":
    main()