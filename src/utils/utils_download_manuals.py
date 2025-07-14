import pandas as pd
import numpy as np
import json, requests, re

def download_manuals(product_number):
    """
    This function downloads all manuals and help resources from the manufacturer's website. The current ingestor expects the following structure:
    [
        {
            "contentType": str,
            "cat1_name": List[str],
            "cat*_name": List[str], # can be cat2 or any other number 
            "url": str,
            "fileBytes": int, # if entry represents pdf file
        },
        ...
    ]
    """
    # implement your manual download logic here
    pass