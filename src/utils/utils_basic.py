class HTTPException(Exception):
    '''
        Standard error class to be used.
    '''
    def __init__(self, status_code:int, detail:str):
        '''
            Initializes the HTTPException with a status code and a detailed error message.

            Args:
                status_code (int): The HTTP status code for the error.
                detail (str): The detailed error message explaining the issue.
        '''
        self.status_code = status_code
        self.detail = detail
