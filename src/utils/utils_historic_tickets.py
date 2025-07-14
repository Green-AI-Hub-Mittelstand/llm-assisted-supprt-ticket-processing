import re
import pandas as pd
from typing import List
from utils.utils_llm import query_llm
from utils.prompt_library import ticket_summarization_system_prompt
from utils.utils_spare_parts import categorize_multiple_spare_parts

def remove_mail_addresses(text:str) -> str:
    '''
        Removing mail addresses from texts.

        Args:
            text (str): The input string containing potential email addresses.
        
        Returns:
            str: A copy of the input text with all email addresses replaced by a space.
    '''
    return re.sub(r"[\w\-\.]+@[\w-]+(\.[a-zA-Z]{2,})+", " ", text)

def process_headlines_1(description:str) -> dict:
    '''
        Parses and organizes text data based on specific headline patterns. The function uses regular expressions to 
        identify sections in a given description that follow a consistent header-value format. Each identified section 
        is stored in a dictionary, excluding certain predefined headers and values considered irrelevant for the 
        analysis. Nested structures are created where applicable (indicated by nested dictionaries within keys).

        Args:
            description (str): The text containing multiple headlines following a specific pattern.

        Returns:
            dict: A dictionary with headers as keys and their corresponding values as extracted from the description.
    ''' 
    matches = re.findall(r'([A-Z ]+):\n[=]+\n([\s\S]*?)(?=\n[A-Z ]+:\n[=]+|$)', description)
    matches = {k: v for k, v in matches if v not in ["\n", " ", "null\n"] and k not in ["AGREEMENT", 
                                                                                        "DELIVERY", "PARTORDERS", 
                                                                                        "CONTACT", "ENTITLEMENT", 
                                                                                        "PARTS SHIPPED TO",
                                                                                        "ATTACHMENTS",
                                                                                        "ALTERNATE CONTACT", "WHERE"]}
    for key in matches.keys():
        if key in ["MISC", "WORKORDER", "SKILLSETS", "CASE DETAILS", "CONTACT DETAILS"]:
            matches[key] = dict(re.findall(r"(.*)(?:\s*):(?:\s*(.*))\s*(?=\n|$)", matches[key]))
            # Not checked headlines are always included
    return matches

def process_headlines_2(description:str) -> dict:
    '''
        Parses and organizes text data based on specific headline patterns. The function uses regular expressions to 
        identify sections in a given description that follow a consistent header-value format. Each identified section 
        is stored in a dictionary, excluding certain predefined headers and values considered irrelevant for the 
        analysis.

        Args:
            description (str): The text containing multiple headlines following a specific pattern.

        Returns:
            dict: A dictionary with headers as keys and their corresponding values as extracted from the description.
    '''
    matches = re.findall(r'(?:^|[=]+\n+)\n*([a-zA-Z ]+:){0,1}([\s\S]*?)\n*(?=[=]+\n+|$)', description)
    matches = {k: v for k, v in matches if v not in ["\n", " ", "null\n"] and k not in ["BOOKING DETAILS:", "ACCOUNT:",
                                                                                        "DEVICE:", "CONTACT:",
                                                                                        "SKILLS:", "OTHER:",
                                                                                        "PARTS SHIPPED TO:", 
                                                                                        "Kontakt Terminabstimmung:",
                                                                                        "Additional info  :", 
                                                                                        "Contact Details for Onsite would be  :",
                                                                                        "DISPATCHERS:"]}
    return matches

def transform_dict_to_text(description_dict:dict) -> str:
    '''
        Transform structured dicts to texts including keys and and values

            Args:
                description_dict (dict): A dictionary containing keys that could either be strings or nested 
                    dictionaries.
            
            Returns:
                str: A multi-line string where each key and its associated value are on separate lines, 
                    with sub-dictionaries indented appropriately.
    '''
    text = ""
    for key, value in description_dict.items():
        if isinstance(value, dict):
            text += f"{key}:\n"
            for sub_key, sub_value in value.items():
                text += f"  {sub_key}: {sub_value}\n"
        else:
            text += f"{key}:\n{value}\n\n"
    text = re.sub(r"\n\n\n+", "\n\n", text)
    return text

def process_description_per_row(row:pd.Series) -> str|bool:
    '''
        Processes and transforms the content of a description field within each row from a dataset. The function handles
        multiple formats including mail addresses, specific headlines with varying levels of heading symbols, and 
        tenant-specific conditions (two tenants included). It removes email addresses, processes headlines based on 
        symbol patterns.

        Args:
            row (pd.Series): A series containing data for a single record in the dataset with at least a "description" 
                and "tenantBusinessKey" key.

        Returns:
            str or bool: The processed description. If the condition is met to return False, it returns False. 
                Otherwise, it returns the transformed string.
    '''
    description = row["description"]
    description = remove_mail_addresses(description) # removing mail addresses

    if re.search("[A-Z]+:\n===+\n", description): # Format:  HEADLINE:\n=======\n
        description = process_headlines_1(description)
        description = transform_dict_to_text(description)
    
    elif re.search("=====(\n)+[A-Za-z ]+:", description): # Format:  =====\nHeadline:
        description = process_headlines_2(description)
        description = transform_dict_to_text(description)

    elif len(description) <= 150: # should include enough characters to be properly processed
        description = False

    else:
        pass

    return description


def process_description(description:str, use_min_length:bool=True) -> str|bool:
    '''     
        Processes and transforms the content of a description field within each row from a dataset. The function handles
        multiple formats including mail addresses, specific headlines with varying levels of heading symbols, and 
        tenant-specific conditions (two tenants included). It removes email addresses, processes headlines based on 
        symbol patterns.

        Args:
            description (str): The raw description text to be processed.
            use_min_length (bool): Whether to use a minimum length of 150 characters to check for the processed 
                description.

        Returns:
            str or bool: The processed description. If the condition is met to return False, it returns False. 
                Otherwise, it returns the transformed string.
    '''
    description = remove_mail_addresses(description) # removing mail addresses

    if re.search("[A-Z]+:\n===+\n", description): # Format:  HEADLINE:\n=======\n
        description = process_headlines_1(description)
        description = transform_dict_to_text(description)
    
    elif re.search("=====(\n)+[A-Za-z ]+:", description): # Format:  =====\nHeadline:
        description = process_headlines_2(description)
        description = transform_dict_to_text(description)

    elif use_min_length and len(description) <= 150: # should include enough characters to be properly processed
        description = False

    else:
        pass

    return description

def wrapper_process_description(df:pd.DataFrame) -> pd.DataFrame:
    '''
        This function processes each row in a DataFrame to create or update a "processed_description" column. It then 
        filters out rows where the "processed_description" is not truthy.

        Args:
            df (pd.DataFrame): The input DataFrame containing at least one column named 'description'.

        Returns:
            pd.DataFrame: A new DataFrame identical to the input but with an additional "processed_description" column 
                where each row's description has been processed according to a specific function, and filtered.
    '''
    df["processed_description"] = df.progress_apply(process_description_per_row, axis=1)
    df = df[df["processed_description"].astype(bool)]
    return df

def preprocessing_tickets_v2(tickets:pd.DataFrame) -> pd.DataFrame:
    '''
        Preprocesses ticket data by filtering and cleaning based on specific conditions, including category, 
        subcategory, description, device information, and removing unnecessary columns.
        
        Args:
            tickets (pd.DataFrame): A DataFrame containing ticket data with various attributes.
            
        Returns:
            pd.DataFrame: A cleaned DataFrame after applying the specified filters and transformations.
    '''
    # Preprocessing of ticket data 
    print("Number of tickets in orginial data:", len(tickets))
    tickets = tickets[tickets.ticketCategory.isin(["Break and fix"])]
    print("Number of tickets after filtering category:", len(tickets))
    tickets = tickets[~tickets.ticketsubCategory.isin(["Return Travel", "Test Ticket"])]
    print("Number of tickets after filtering SUBcategory:", len(tickets))
    tickets = tickets[~((tickets.description == "Test") |
                        (tickets.description == "test") |
                        (tickets.reportWorknote == "Test") |
                        (tickets.reportWorknote == "test"))]
    tickets = tickets[~tickets.ticketId.isin([130721, 628575])]
    print("Number of tickets after filtering for tests:", len(tickets))
    tickets = tickets[~(tickets.deviceType.isna() | tickets.deviceModel.isna())]
    print("Number of tickets after removing missing device information:", len(tickets))
    tickets = tickets.drop(["recallCount", "InterventionCount"], axis=1)
    tickets = tickets.drop(["reportedDuration", "estimatedDuration", "projectName", 
                            "ticketCategory", "deviceSubcategory", "ticketsubCategory"], axis=1) # Not needed
    print("Number of tickets after processing:", len(tickets))

    # Change some types
    tickets.description = tickets.description.str.replace("\r\n", "\n") # sometimes \r included which hinders processing
    tickets.reportIsRemoteSolved = tickets.reportIsRemoteSolved.astype(bool)
    tickets.reportIsSuccessful = tickets.reportIsSuccessful.astype(bool)
    tickets.ticketCreated = pd.to_datetime(tickets.ticketCreated, format='ISO8601')
    tickets.resourceId = tickets.resourceId.astype(str)

    return tickets

def summarize_historic_ticket(description:str, worknote:str, success:bool, remoteFix:bool, spare_parts:List[str], 
                              model:str, categorize_spare_parts:bool=True) -> str: 
    '''
        Summarize the key details from an IT support ticket description and a technician's worknote, extracting the 
        problem and solution (if applicable).

        Args:
            description (str): The description provided by the user regarding the issue they are experiencing with their 
                IT system.
            worknote (str): A note written by the technician detailing the steps taken to address or resolve the problem 
                described in the ticket.
            success (bool): Indicates whether the solution attempt was successful. True if successful, False otherwise.
            remoteFix (bool): Indicates whether the problem was solved remotely. True if remotely, Fals if on-site.
            spare_parts (list[str]): The spare parts used for the tickets. Only include parts that were actually used.
            model (str): The AI model to be used for generating the summary.
            categorize_spare_parts (bool, optional): Whether a LLM should categorize the spare parts for preprocessing.

        Returns:
            str: A plain text summary of the ticket description and worknote. The spare parts are appended to the text.
    '''

    prompt = """
    Description:
    {}

    Worknote:
    {}

    Successful?:
    {}

    Remote fix?:
    {}
    """.format(description, worknote, success, remoteFix)

    response = query_llm(user_prompt=prompt,
                         system_prompt=ticket_summarization_system_prompt,
                         model=model,
                         prefill="Here is your summarization of the support ticket description and worknote: ")
    
    if categorize_spare_parts and len(spare_parts) > 0:
        spare_parts = categorize_multiple_spare_parts(spare_parts=spare_parts)
    response = response + "\nSpare Parts used:\n" + str(spare_parts)

    return response.strip()

def wrapper_summarize_historic_ticket(df:pd.DataFrame, col_description:str="processed_description", 
                                      col_worknote:str="reportWorknote", col_success:str="reportIsSuccessful", 
                                      model:str="llama3.2:3b") -> pd.DataFrame:
    '''
        This function is used to summarize historic tickets by applying the 'summarize_historic_ticket' function 
        row-wise on a dataframe.
    
        Args:
            df (pd.DataFrame): The input DataFrame that contains the historical ticket data.
            col_description (str): The name of the column in the DataFrame containing the description of each historic 
                ticket. Default is "processed_description".
            col_worknote (str): The name of the column in the DataFrame containing the worknotes for each historic 
                ticket. Default is "reportWorknote".
            col_success (str): The name of the column in the DataFrame indicating whether each historic ticket was 
                successful or not. Default is "reportIsSuccessful".
            model (str): The model to be used for summarization. Default is "llama3.2:3b".
        
        Returns:
            pd.DataFrame: The input DataFrame with an additional column 'processed_description' that contains the 
                summarized ticket information.
    '''
    def row_wise(row):
        description = row[col_description]
        worknote = row[col_worknote]
        success = row[col_success]
        return summarize_historic_ticket(description, worknote, success, model=model)
    
    df["processed_description"] = df.progress_apply(row_wise, axis=1)
    return df