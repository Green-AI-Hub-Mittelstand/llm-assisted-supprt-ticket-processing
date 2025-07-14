from typing import List, Tuple, Set
import re
from pgvector.psycopg import register_vector
from utils.utils_llm import generate_embeddings
from utils.utils_db import get_psycopg_client
import os
import ollama


def determine_relevancy(manual: dict) -> bool:
    """
    Determines the relevancy of a document by assessing metadata.
    
    Parameters:
        metadata (dict): A dictionary containing metadata on the document.
    
    Returns:
        bool: True if the document is relevant, else False.
    """
    # Keywords to identify relevant documents
    relevant_keywords = [
        "maintenance", "repair", "troubleshooting", "service", 
        "diagnostics", "troubleshoot"
    ]
    relevant_fields = ["contentType"] + \
        [key for key in manual.keys() if re.search(r"cat\d*_name", key)]
    

    # Check relevancy in prioritized fields
    for field in relevant_fields:
        value = manual.get(field)
        if isinstance(value, str) and any(keyword in value.lower() for keyword in relevant_keywords):
            return True
    return False


def add_manual_chunks_to_db(chunks:List[dict], devicetype:str , url: str, deviceModel_used: bool, collection_name:str="manuals", doc_type:str="pdf") -> None:
    """
    Adds a list of chunks to a vector databse.
    
    This function connects to a PostgreSQL database and ensures that the specified table exists. If the table does not exist, it is created according to a specified table schema. The chunks are then inserted into this collection.
    
    Parameters:
        chunks (List[dict]): A list of dictionaries where each dictionary represents a chunk of text with metadata including its page number and other relevant information.
        devicetype (str): The type of device associated with the manual or document these chunks belong to.
        url (str): The URL from which the PDF was sourced.
        deviceModel_used (bool): Indicates whether the specific device model is mentioned in the text of any chunk.
        collection_name (str, optional): The name of the table where the chunks will be stored. Defaults to "manuals".
    
    Returns:
        None
    """

    try:
        client = get_psycopg_client()

        client.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        register_vector(client)
        client.execute("""CREATE TABLE IF NOT EXISTS manuals (
               id bigserial PRIMARY KEY,
               chunk text,
               chunk_embedding vector(512),
               page_number integer,
               deviceType text,
               deviceModel_used boolean,
               url text,
               docType text,
               created_at timestamp DEFAULT CURRENT_TIMESTAMP
               );""")
        chunk_list = list()
        for chunk in chunks:
            chunk_embedding = (chunk["embedding"] 
                               if "embedding" in chunk.keys()
                               else generate_embeddings(input_text=chunk["text"], dimensions=512))
            chunk_embedding = f"[{','.join(map(str, chunk_embedding))}]"
            dp = {
                "chunk": chunk["text"],
                "chunk_embedding": chunk_embedding,
                "deviceType": devicetype,
                "page_number": chunk["page_no"],
                "url": url,
                "deviceModel_used": deviceModel_used,
                "docType": doc_type
            }
            chunk_list.append(dp)
        query = """INSERT INTO manuals
               (chunk, chunk_embedding, page_number, deviceType, deviceModel_used, url, docType)
               VALUES (%(chunk)s, %(chunk_embedding)s, %(page_number)s, %(deviceType)s, %(deviceModel_used)s, %(url)s, %(docType)s);"""
        with client.cursor() as cur:
            cur.executemany(query, chunk_list)
    except Exception as e:
        print(e)
    finally:
        client.close()

def add_ticket_to_db(ticket: str, devicetype: str, ticketID: str, collection_name:str="tickets") -> None:
    """
    Adds a ticket to the specified PostgreSQL Table.
    
    This function connects to an instance of PostgreSQL with pgvector and ensures that the specified table exists. If the table does not exist, it is created according to a specified table schema. The ticket is then inserted into this table.
    
    Parameters:
        ticket (str): The summarized content of the ticket.
        devicetype (str): The type of device associated with the ticket.
        ticketID (str): The ID of the ticket
        collection_name (str, optional): The name of the PostgreSQL table where the tickets will be stored. Defaults to "tickets".
    
    Returns:
        None
    """
    
    try:
        client = get_psycopg_client()
        client.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        register_vector(client)
        client.execute("""CREATE TABLE IF NOT EXISTS tickets
               (id bigserial PRIMARY KEY,
               chunk text,
               chunk_embedding vector(512),
               deviceType text,
               ticketID text,
                created_at timestamp DEFAULT CURRENT_TIMESTAMP
               );""")
        chunk_embedding = generate_embeddings(input_text=ticket, dimensions=512)
        chunk_embedding = f"[{','.join(map(str, chunk_embedding))}]"
        dp = {
            "chunk": ticket,
            "chunk_embedding": chunk_embedding,
            "deviceType": devicetype,
            "ticketID": ticketID,
        }
        client.execute("""INSERT INTO tickets
               (chunk, chunk_embedding, deviceType, ticketID)
               VALUES (%s, %s, %s, %s);""",
                       (dp.get("chunk"), dp.get("chunk_embedding"), dp.get("deviceType"), dp.get("ticketID")))
    except Exception as e:
        print(e)
    finally:
        client.close()       