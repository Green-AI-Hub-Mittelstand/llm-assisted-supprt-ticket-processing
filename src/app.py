from app_coordinator_function import process_ticket, NewTicket
import json, os
from fastapi import FastAPI
from pydantic import BaseModel
from utils.utils_basic import HTTPException

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = os.environ.get("PORT", "8000")
app = FastAPI()

@app.post('/process_ticket')
def handler(newTicket:NewTicket):
    print("Started handler!")
    try:
        response = process_ticket(newTicket)
        return {"statusCode":200,
                "body":response}
    
    except HTTPException as e:
        return {"statusCode":e.status_code,
                "body":e.detail}
    
    except Exception as e:
        return {"statusCode":500,
                "body":str(e)}
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host=str(HOST), port=int(PORT))