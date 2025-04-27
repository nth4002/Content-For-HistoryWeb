from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
import os

# Assuming your parser.py is in the same directory
from parser import parse_quiz_lines, read_docx_file, read_odt_file, read_txt_file
from db import processed_odt_file, insert_to_db
import logging
from contextlib import asynccontextmanager
logging.basicConfig(filename="app.log", level=logging.INFO)

import json
from bson import ObjectId

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables and MongoDB vector store when the FastAPI server starts"""
    logging.info("Database tables and vector store initialized successfully")
    yield
    # Cleanup: Delete the MongoDB collection on shutdown
    logging.info("Shutting down server, deleting MongoDB vector store collection...")
    # if delete_collection():
    #     logging.info("MongoDB vector store collection deleted successfully during shutdown")
    # else:
    #     logging.error("Failed to delete MongoDB store collection during shutdown")    
    # print("App shutdown: Deleting MongoDB collections...")
    # result = delete_logs_and_documents_collections()
    # if result:
    #     logging.info(f"Chatbot database deleted successfully during shutdown")
    # else:
    #     logging.error("Failed to delete Chatbot database during shutdown")
    # logging.info(f"Cleanup done: {result}")

app = FastAPI(lifespan=lifespan)

# Configure CORS
origins = [
    "http://localhost:3000",
    # Add your frontend production URL here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def convert_objectid_to_str(data):
    """
    Recursively traverses a dictionary or list and converts
    bson.ObjectId objects to their string representation.
    """
    if isinstance(data, list):
        return [convert_objectid_to_str(item) for item in data]
    elif isinstance(data, dict):
        # Create a new dict to avoid modifying the original during iteration
        new_dict = {}
        for key, value in data.items():
            new_dict[key] = convert_objectid_to_str(value)
        return new_dict
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        # Keep other types as they are
        return data
    
@app.post("/upload/") # Renamed endpoint to be more general
async def upload_quiz_file(file: UploadFile = File(...)):
    """
    Receives a .docx, .odt, or .txt file, parses it into quiz data,
    and returns the data as JSON.
    """
    file_extension = os.path.splitext(file.filename)[1].lower()

    # Read the file content as bytes FIRST, as this is needed for all readers
    try:
        file_bytes = await file.read()
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Error reading uploaded file: {e}")


    # Choose the correct reader based on file extension
    lines_list = []
    try:
        if file_extension == '.docx':
            lines_list = read_docx_file(file_bytes)
        elif file_extension == '.odt':
            lines_list = read_odt_file(file_bytes)
            print("Read successfully!")
        elif file_extension == '.txt':
            lines_list = read_txt_file(file_bytes)
        else:
            # If extension is not supported, raise an error early
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}. Please upload .docx, .odt, or .txt.")

    except ValueError as ve:
        # Catch errors specifically from the file reading functions
         raise HTTPException(status_code=400, detail=f"File reading/decoding error for {file_extension}: {ve}")
    except Exception as e:
        # Catch any unexpected errors during reading
        raise HTTPException(status_code=500, detail=f"An internal error occurred during file reading: {e}")


    # Pass the list of lines to the generic parser
    try:
        # print("Line list\n", lines_list)
        # parsed_data = parse_quiz_lines(lines_list)
        my_dicts = processed_odt_file(file_bytes)
        insert_to_db(my_dicts)
        result_dict = my_dicts[0]
        serializable_result = convert_objectid_to_str(result_dict) # Convert ObjectId to str
        return serializable_result # Return the fully serializable dictionary
    except ValueError as ve:
        # Catch specific errors from the parser (e.g., format issues)
        raise HTTPException(status_code=400, detail=f"Parsing error: {ve}")
    except Exception as e:
        # Catch any other unexpected errors during parsing
        raise HTTPException(status_code=500, detail=f"An internal error occurred during parsing: {e}")


@app.get("/")
async def read_root():
    return {"message": "FastAPI server is running. Use /upload to upload .docx, .odt, or .txt quiz files."}