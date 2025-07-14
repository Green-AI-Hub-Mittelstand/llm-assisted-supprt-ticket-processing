from coordinator.utils import generate_summary_query_string, retrieve_context

from utils.utils_historic_tickets import process_description
from utils.utils_llm import query_main_llm, query_llm
from utils.utils_basic import HTTPException

from pydantic import BaseModel
import os, json

MODEL_NAME_MAIN_QUERY = os.environ.get("MODEL_NAME_MAIN_QUERY", "amazon.nova-lite-v1:0")
MODEL_NAME_QUERY_STRING = os.environ.get("MODEL_NAME_QUERY_STRING", "amazon.nova-micro-v1:0")

print("Info: Model for main query is", MODEL_NAME_MAIN_QUERY)
print("Info: Model for query string is", MODEL_NAME_QUERY_STRING)

class NewTicket(BaseModel):
    '''
        Model for the expected new ticket input.
    '''
    description: str
    deviceType: str

def process_context(context:dict) -> dict:
    """
    Function to preprocess retrieved context for final HTML response.
    
    Args:
        context: The fully retrieved context returned from the retrieve_context function
    
    Returns:
        dict: a cleaned version of the retrieved context
    """
    tickets = context["tickets"]
    manuals = context["manuals"]
    new_tickets = [ticket["ticketId"] for ticket in tickets]
    new_manuals = [{
        "id": manual["id"],
        "url": manual["url"],
        "page_number": manual["page_number"],
        "doctype": manual["doctype"]
    } for manual in manuals]
    return {"tickets": new_tickets, "manuals": new_manuals}

def process_ticket(new_ticket:NewTicket) -> dict:
    print("Processing of ticket started...")
    try:
        new_ticket = NewTicket.model_validate(new_ticket)
        # input: description + deviceType
        description_org = new_ticket.description
        deviceType = new_ticket.deviceType
        print("-> Validated input ticket.")
        # preprocessing of description
        description = process_description(description_org, use_min_length=False)
        print("-> Preprocessed description.")
        # generate summary_query_string
        summary_json = generate_summary_query_string(description, model=MODEL_NAME_QUERY_STRING) # No fallback for wrong json
        print("-> Generated summary json.")
        # retrieve context using query string
        retrieved_context = retrieve_context(summary_json.query_string, deviceType)
        print("-> Retrieved context.")
        # query LLM with context and summarized description
        response = query_main_llm(description, retrieved_context, model=MODEL_NAME_MAIN_QUERY) # No fallback for wrong json
        print("-> Queried main LLM.")
        response = response.model_dump()
        response["summary_json"] = summary_json.model_dump()
        retrieved_context = process_context(retrieved_context)
        response["context"] = retrieved_context
        print("-> Done.")
        return response
    
    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unknown error occured while processing. Error message:" + str(e))