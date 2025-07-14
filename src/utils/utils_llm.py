import ollama
from pydantic import BaseModel
from typing import List
import re, os, json, boto3
from botocore.client import BaseClient
import pydantic
from utils.prompt_library import main_query_system_prompt
from utils.utils_basic import HTTPException

LLM_ENV = os.environ.get("LLM_ENV", "local")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", None)
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", None)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_NAME_VECTORIZER = os.environ.get("MODEL_NAME_VECTORIZER", "amazon.titan-embed-text-v2:0")
IS_LAMBDA_HANDLER = True if os.environ.get("IS_LAMBDA_HANDLER", "no") == "yes" else False

def get_bedrock_client() -> BaseClient:
    '''
        Returns a Boto3 client for AWS Bedrock service.
    
        Returns:
            BaseClient: A Boto3 client for the AWS Bedrock service.
    '''
    try:
        print(f"-> Creating client ({str(IS_LAMBDA_HANDLER)})...")
        if IS_LAMBDA_HANDLER:
            bedrock_client = boto3.client('bedrock-runtime')

        else:
            if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
                bedrock_client = boto3.client(  'bedrock-runtime', 
                                                aws_access_key_id=AWS_ACCESS_KEY_ID,
                                                aws_secret_access_key=AWS_SECRET_ACCESS_KEY, 
                                                region_name=AWS_REGION
                                                )
            else:
                raise HTTPException(status_code=403, detail="AWS credentials not provided")
            
        print("-> Client created")
        return bedrock_client
    
    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(status_code=500, 
                            detail="Error ocured while creating the Bedrock client. Maybe check IS_LAMBDA_HANDLER. "
                            "Error message: "+ str(e))

def query_llm(user_prompt:str, model:str, system_prompt:str=None, prefill:str='Here is the JSON response: ```json', 
              output_format=None) -> str:
    '''
        Queries a language model to generate a response based on the given user prompt.

        Args:
            user_prompt (str): The prompt provided by the user.
            model (str): The name of the language model to use for generating the response.
            system_prompt (str, optional): A system prompt that provides additional context or instructions to the 
                language model. Defaults to None.
            prefill (str, optional): A string to be prefilled in the generated response. Defaults to 'Here is the JSON 
                response: ```json', allowing easy use with json.
            output_format (any, optional): The desired format of the output. Defaults to None. Not applicable to all 
                models.

        Returns:
            str: The generated response from the language model. If the prefill contains "```json" some processing will 
                be done to allow better output.
    '''
    try:
        if LLM_ENV=="aws":
            bedrock_client = get_bedrock_client()
            if 'amazon.nova' in model:
                request_body = {'system': [
                                    {'text': system_prompt}
                                    ],
                                'messages': [
                                    {'role': 'user', 'content': [{'text': user_prompt}]}, 
                                    {'role': 'assistant', 'content': [{'text': prefill}]}
                                    ]
                                }
                response = bedrock_client.invoke_model(modelId=model,
                                                    body=json.dumps(request_body))
                response_body = response['body'].read()
                response_body = json.loads(response_body.decode('utf-8'))
                response_text = response_body['output']['message']['content'][0]['text']
            
            elif 'meta.llama' in model:
                prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

                {system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

                {user_prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>{prefill}
                
                """.format(system_prompt=system_prompt, user_prompt=user_prompt, prefill=prefill)

                request_body = {'prompt': prompt
                                }
                response = bedrock_client.invoke_model( body=json.dumps(request_body),
                                                        modelId=model)
                response_body = json.loads(response.get('body').read())
                response_text = response_body['generation']

            elif 'anthropic.claude' in model:
                request_body = {'anthropic_version': 'bedrock-2023-05-31',
                                'max_tokens': 512,
                                'system': [
                                    {'type': 'text', 'text': system_prompt}
                                    ],
                                'messages': [
                                    {'role': 'user', 'content': [{'type': 'text', 'text': user_prompt}]},
                                    {'role': 'assistant', 'content': [{'type': 'text', 'text': prefill}]}
                                    ],
                                }
                response = bedrock_client.invoke_model( modelId=model,
                                                        body=json.dumps(request_body))
                response_body = json.loads(response.get('body').read())
                response_text = response_body["content"][0]["text"]
            if "```json" in prefill:
                response_text = f'```json{response_text}'
                response_text = response_text.replace('\n', ' ')
                response_text = response_text.replace('True', 'true')
                response_text = response_text.replace('False', 'false')

        elif LLM_ENV=="local":
            if not system_prompt: system_prompt = ""
            final_prompt = """
            <|begin_of_text|><|start_header_id|>system<|end_header_id|>

            {sys_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>

            {description_and_context}<|eot_id|><|start_header_id|>assistant<|end_header_id|>```json

            """.format(sys_prompt=system_prompt, description_and_context=user_prompt).strip()

            response = ollama.generate(model=model, prompt=final_prompt, format=output_format)
            response_text = response["response"]
        
        else:
            raise HTTPException(status_code=501, detail=f"Invalid LLM environment specified: {LLM_ENV}. Please set "
                                "LLM_ENV to 'aws' or 'local'.")
        return response_text

    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occured accessing {LLM_ENV} LLM. Error message:" + str(e))

class MainReponse(BaseModel):
    '''
        Model for the expected main response of the LLM.
    '''
    issue: str
    cause: str
    remoteFix: bool
    solution: str
    spareParts: List[str]

def query_main_llm(description:str, context:dict, model:str="llama3.2:3b") -> pydantic.BaseModel:
    """
        Processes an IT problem description and its context using a language model to propose a solution.

        Args:
            description (str): A description of the customer's IT problem.
            context (dict): Additional context information, including historic tickets, worknotes, and manual extracts.
            model (str, optional): The name of the language model to use. Defaults to "llama3.2:3b".

        Returns:
            pydantic.BaseModel: A pydantic BaseModel object containing:
                - `issue` (str): A brief summary of the IT problem.
                - `cause` (str): The root cause of the issue.
                - `remoteFix` (bool): Whether the problem can be solved remotely.
                - `solution` (str): A proposed solution to the IT problem.
                - `spareParts` (list[str]): A list of necessary spare parts, if applicable.
    """
    context = {
        "tickets": [obj["chunk"] for obj in context["tickets"]],
        "manuals": [obj["chunk"] for obj in context["manuals"]]
    }
    prompt = prepare_main_prommpt(description, context)

    response = query_llm(user_prompt=prompt, 
                         model=model, 
                         system_prompt=main_query_system_prompt, 
                         output_format=MainReponse.model_json_schema())
    
    json_content = re.search(r'```json(.*?)```', response, re.DOTALL)
    if json_content:
        response = json_content.group(1)

    try:
        validated_response = MainReponse.model_validate_json(response)
    except Exception as e:
        print(response)
        raise HTTPException(status_code=500, detail="LLM did not provide correct JSON.")
    
    return validated_response

def prepare_main_prommpt(description:str, context:str) -> str:
    '''
        Prepares the main prompt for querying a language model. This prompt includes both the description of the IT 
        problem and any relevant context.

        Args:
            description (str): The description of the customer's IT problem.
            context (str): Additional context information, including historic tickets, worknotes, and manual extracts.

        Returns:
            str: The prepared main prompt combining the description and context.
    '''
    manuals = """"""
    for manual in context["manuals"]:
        manuals += manual + "\n"
    tickets = """"""
    for ticket in context["tickets"]:
        tickets += ticket + "\n"
    prompt = """
    Support ticket:
    {}

    Support documents:
    Historic tickets:
    {}

    Manual excerpts:
    {}
    """.format(description, tickets, manuals)
    return prompt

def generate_embeddings(input_text:str, normalize:bool=True, dimensions:int=512) -> list[float]:
    '''
        Generates an embedding for the provided input text using the specified environment (AWS or local).

        The function uses either AWS Bedrock or a local embedding model (e.g., Ollama) to generate a numerical 
        representation of the input text. The returned embedding is typically a list of floats.

        Args:
            input_text (str): The text input for which the embedding is to be generated.
            normalize (bool, optional): Whether to normalize the embedding. Defaults to True.
            dimensions (int, optional): The number of dimensions for the embedding. Defaults to 512.

        Returns:
            List[float]: A list of floating-point numbers representing the generated embedding.
    '''
    try:
        if LLM_ENV=="aws":
            bedrock_client = get_bedrock_client()
            request_body = {'inputText':input_text,
                            'normalize':normalize,
                            'dimensions':dimensions}

            response = bedrock_client.invoke_model( modelId=MODEL_NAME_VECTORIZER,
                                                    body=json.dumps(request_body))
            response_body = json.loads(response.get('body').read())
            embedding = response_body['embedding']

        elif LLM_ENV=="local":
            embedding = ollama.embed(model="nomic-embed-text", input=input_text)["embeddings"][0]
            
        else:
            raise HTTPException(status_code=501, detail=f"Invalid LLM environment specified: {LLM_ENV}. Please set "
                                                         "LLM_ENV to 'aws' or 'local'.")

        return embedding

    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occured accessing {LLM_ENV} LLM to generate embedding. "
                                                     "Error message:" + str(e))

