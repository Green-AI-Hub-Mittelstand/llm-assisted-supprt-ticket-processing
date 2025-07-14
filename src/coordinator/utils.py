from pydantic import BaseModel, Field
import json
import re
import psycopg
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector
from typing import List

import pydantic

from utils.prompt_library import query_string_system_prompt
from utils.utils_llm import generate_embeddings, query_llm
from utils.utils_db import get_psycopg_client
import struct
#import pyodbc

class SummaryResponse(BaseModel):
    description: str = Field(description="A concise summary of the problem.")
    query_string: str = Field(
        description="A query string for the vector database constructed from relevant keywords.")


def generate_summary_query_string(description: str, model="llama3.2:3B") -> pydantic.BaseModel|None:
    """
    Generates a concise summary of the problem and constructs a corresponding query string for a vector database.

    This function reads an instruction prompt from a file, formats it with the provided description, sends it to an AI model, 
    and processes the response to extract a JSON object containing the summary description and 
    the constructed query string. The JSON object is then validated against the `SummaryResponse` Pydantic model.

    Args:
        description (str): A detailed description of the problem or task for which a summary and query string are needed.
        model (str, optional): The name of the AI model to be used for generating the summary and query string. Defaults to "llama3.2:3B".

    Returns:
        dict|None: A dictionary containing the validated summary description and query string if successful, otherwise None.
    """
    json_string = json.dumps({
        "description": "A concise summary of the problem. Approximately 2 sentences.",
        "query_string": "A query string for the vector database constructed from relevant keywords."
    })

    instruction_prompt = query_string_system_prompt.replace(
        "{format_instructions}", json_string)
    response = query_llm(user_prompt=description,
                         model=model,
                         system_prompt=instruction_prompt,
                         output_format=SummaryResponse.model_json_schema())
    json_content = re.search(r'```json(.*?)```', response, re.DOTALL)
    if json_content:
        response = json_content.group(1)
    validated_response = SummaryResponse.model_validate_json(response)

    return validated_response



def retrieve_context(query_string: str, deviceType: str) -> dict[list]:
    """
    Retrieves context from a vector database based on a given query string and device type.

    This function connects to a vector database (here a PostgreSQL database with the pgvector extension enabled), then performs hybrid queries using the a constructed query string. 
    The queries will return 5 histrocial tickets and 5 entries from manufacturer support resources that are related to the submitted ticket.

    Args:
        query_string (str): A search query string used to retrieve relevant context from vector databases.
        deviceType (str): The type of device for which the context should be filtered.

    Returns:
        dict[list]: A dictionary containing two lists - 'tickets' and 'manuals', each holding chunks of information retrieved from their respective collections based on the query string and device type.
    """
    client = get_psycopg_client()

    print("-> Created db client.")
    try:
        register_vector(client)
        embedding_str = generate_embeddings(input_text=query_string, dimensions=512)
        embedding_str = f"'[{','.join(map(str, embedding_str))}]'::vector"
        manuals_query = generate_sql_query(
            table_name="manuals", query_str=query_string, embedding_str=embedding_str, deviceType=deviceType)
        ticket_query = generate_sql_query(
            table_name="tickets", query_str=query_string, embedding_str=embedding_str)
        with client.cursor(row_factory=dict_row) as cur:
            cur.execute(manuals_query)
            manuals = cur.fetchall()
            cur.execute(ticket_query)
            tickets = cur.fetchall()
    except Exception as e:
        raise e
    finally:
        client.close()

    # reverse order of retrieved context chunks to exploit recency bias in LLMs
    return {
        "tickets": tickets,
        "manuals": manuals
    }


def generate_sql_query(table_name: str, query_str: str, embedding_str: str, limit: int = 5, deviceType: str = None):
    """
    Generates a SQL query string for retrieving context from vector databases.

    This function constructs a hybrid SQL query that uses both semantic similarity (vector search) and full-text search to retrieve relevant
    chunks of information. The query is tailored based on the specified table name, query string, embedding string, limit, and optionally,
    device type.

    Args:
        table_name (str): The name of the database table from which to retrieve context.
        query_str (str): A text-based search query used for full-text search.
        embedding_str (str): A vector representation of the query string used for semantic similarity search.
        limit (int, optional): The maximum number of results to return. Defaults to 5.
        deviceType (str, optional): The type of device for which the context should be filtered. Defaults to None.

    Returns:
        str: A SQL query string constructed based on the provided parameters.
    """
    translate_table = str.maketrans(
        {'"': r'', "\\": r"", "%": r"", "_": r"", "'": r""})
    query_str = query_str.translate(translate_table)
    sql_query = """SELECT
    searches.id,
    searches.chunk, """
    if table_name == "tickets":
        sql_query += """searches.ticketID,"""
    else:
        sql_query += """searches.page_number,
        searches.url,
        searches.docType,"""
    sql_query += """sum(rrf_score(searches.rank::int)) AS score
FROM (
	(
		SELECT
            id,
            chunk,"""
    if table_name == "tickets":
        sql_query += """ticketID,"""
    else:
        sql_query += """page_number,
        url,
        docType,"""
    sql_query += """rank() OVER (ORDER BY {embedding_str} <=> chunk_embedding)::int AS rank
		FROM {table_name}
        """.format(embedding_str=embedding_str, table_name=table_name)
    if table_name == "manuals":
        sql_query += """WHERE deviceType = '{deviceType}' """.format(
            deviceType=deviceType)
    sql_query += """ORDER BY rank
		LIMIT 40
	)""".format(embedding_str=embedding_str)
    sql_query += """UNION ALL
	(
		SELECT
			id,
            chunk,"""
    if table_name == "tickets":
        sql_query += """ticketID,"""
    else:
        sql_query += """page_number,
        url,
        docType,"""
    sql_query += """rank() OVER (ORDER BY ts_rank_cd(to_tsvector(chunk), plainto_tsquery('{search_string}')) DESC) AS rank
		FROM {table_name}
		WHERE""".format(table_name=table_name, search_string=query_str)
    if table_name == "manuals":
        sql_query += """ deviceType ='{deviceType}' AND """.format(
            deviceType=deviceType)
    sql_query += """ plainto_tsquery('english', '{search_string}') @@ to_tsvector('english', chunk)
		ORDER BY rank
		LIMIT 40
	)
) searches """.format(search_string=query_str)
    sql_query += """GROUP BY searches.id, searches.chunk,"""
    if table_name == "tickets":
        sql_query += """searches.ticketID """
    else:
        sql_query += """searches.page_number, searches.url, searches.docType """
    sql_query += """ORDER BY score DESC
    LIMIT {limit};""".format(limit=limit)
    sql_query = sql_query.replace("\n", " ").replace("\t", " ")
    return sql_query

def handle_datetimeoffset(dto_value):
    # ref: https://github.com/mkleehammer/pyodbc/issues/134#issuecomment-281739794
    # e.g., (2017, 3, 16, 10, 35, 18, 0, -6, 0)
    tup = struct.unpack("<6hI2h", dto_value)
    tweaked = [tup[i] // 100 if i == 6 else tup[i] for i in range(len(tup))]
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:07d} {:+03d}:{:02d}".format(*tweaked)


