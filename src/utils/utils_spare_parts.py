import json
import os, re
import pandas as pd
from pydantic import BaseModel
from typing import List
from utils.utils_llm import query_llm
from utils.prompt_library import categorize_spare_part_prompt
from utils.utils_basic import HTTPException

MODEL_NAME_CATEGORIZE_SPARE_PARTS = os.environ.get("MODEL_NAME_CATEGORIZE_SPARE_PARTS", "amazon.nova-micro-v1:0")

class CategroyResponse(BaseModel):
    spareParts: List[str]

def categorize_multiple_spare_parts(spare_parts: list[str],) -> list:
    '''
        Prompts LLM to classify parts. 

        Args:
            spare_parts (list[str]): Spare parts to classify.

        Returns:
            List[str]: List containing the categories of each spare part.
    '''
    if not all(isinstance(item, str) for item in spare_parts):
        raise HTTPException(status_code=422, detail="All items in the list of spare parts must be strings!")

    user_prompt = f"Input: {spare_parts}"
    response = query_llm(user_prompt=user_prompt,
                         model=MODEL_NAME_CATEGORIZE_SPARE_PARTS,
                         system_prompt=categorize_spare_part_prompt)
    json_content = re.search(r'```json(.*?)```', response, re.DOTALL)
    if json_content:
        response = json_content.group(1)

    try:
        validated_response = CategroyResponse.model_validate_json(response)
    except Exception as e:
        print(response)
        raise HTTPException(status_code=500, detail="LLM did not provide correct JSON (cat).")
    return validated_response.spareParts

def load_data(path:str) -> list[str]:
    '''
        Loads data from csv file.

        Args: 
            path (str): Path where data is saved.

        Returns:
            column_data (list[str]): Data from 'partDescription' column.
    '''
    df = pd.read_csv(path)  
    column_name = 'partDescription'  
    column_data = df[column_name].astype(str).unique().tolist()

    return column_data