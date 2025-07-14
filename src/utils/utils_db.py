from utils.utils_basic import HTTPException
import os, psycopg, pyodbc
from typing import List, Set
import pandas as pd
import struct

DB_ENV = os.getenv("DB_ENV", "local")
DBHOST = os.getenv("DBHOST", "localhost")
DBUSER = os.getenv("DBUSER", "postgres")
DBPW = os.getenv("DBPW", "password")
DBPORT = os.getenv("DBPORT", "5432")

FCHOST = os.getenv("FCHOST", None)
FCUSER = os.getenv("FCUSER", None)
FCPW = os.getenv("FCPW", None)
FCDB = os.getenv("FCDB", None)
FCPORT = os.getenv("FCPORT", "1433")

def get_psycopg_client():
    '''
        Returns a psycopg connection object to the appropriate database based on the current environment.

        If DB_ENV is set to 'local', connects to a local PostgreSQL database using the credentials stored in
        the environment variables. If DB_ENV is set to any other value, attempts to connect to an AWS RDS
        instance using the provided credentials.

        Returns:
            psycopgconnection: A psycopg connection object.
    '''
    try:
        if DB_ENV in ["local", "aws"]:
            client = psycopg.connect(host=DBHOST,
                                    user=DBUSER,
                                    password=DBPW,
                                    port=DBPORT,
                                    connect_timeout=10,
                                    autocommit=True
                                    )
            return client
        else:
            raise HTTPException(status_code=501, detail="Invalid db environment specified. Please set DB_ENV to 'aws' or 'local'.")
    
    except HTTPException as e:
        raise e
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error occured connecting to {DB_ENV} db client with psycopg. Error message:" + str(e))
    

def handle_datetimeoffset(dto_value):
    # ref: https://github.com/mkleehammer/pyodbc/issues/134#issuecomment-281739794
    # e.g., (2017, 3, 16, 10, 35, 18, 0, -6, 0)
    tup = struct.unpack("<6hI2h", dto_value)
    tweaked = [tup[i] // 100 if i == 6 else tup[i] for i in range(len(tup))]
    return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:07d} {:+03d}:{:02d}".format(*tweaked)

def get_productiondb_client():
    # This function is a placeholder it should contain functionality to connect to a production db that holds the support tickets
    pass


def get_consumed_parts(ticketId:str) -> List[dict]:
    # This function serves as a placeholder to retrieve the spare parts used during ticket solving
    pass
