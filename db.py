import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure, PyMongoError
from bson import ObjectId
from bson import json_util # Import json_util for BSON serialization
import time
from parser import read_odt_file, parse_quiz_lines
from dotenv import find_dotenv, load_dotenv
# No need to import json if only using json_util for pymongo results

load_dotenv(find_dotenv(), override=True)
# --- Configuration (use environment variables) ---
MONGO_URI = os.getenv("MONGODB_URI")
MONGO_TEST_DB = "History_Heritage_Database"
MONGO_TEST_COLLECTION = "knowledgeTest"

# --- Connection and Test Operations Snippet ---

# Example Usage (for testing the parser logic directly)
folder_dir = '/home/phucuy2025/HRS_Project/Content-Creator/content'
folder_dir_2 = '/home/phucuy2025/HRS_Project/Content-Creator/content_2'
folder_lst = [folder_dir, folder_dir_2]
def processed_odt_file(odt_file_bytes):
    my_dicts = []
    line_lst = read_odt_file(odt_file_bytes=odt_file_bytes)
    parsed_data_odt_simulated = parse_quiz_lines(line_lst)
    my_dict=parsed_data_odt_simulated[0]
    my_dicts.append(my_dict)
    # for key, value in my_dict.items():
    #     print(f"{key}, : {value}")
    return my_dicts

def insert_to_db(my_dicts):

    client = None

    print(f"Attempting to connect to MongoDB at: {MONGO_URI}")

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ismaster')
        print("MongoDB connection successful!")

        db = client[MONGO_TEST_DB]
        collection = db[MONGO_TEST_COLLECTION]
        print(f"Using database '{MONGO_TEST_DB}' and collection '{MONGO_TEST_COLLECTION}'")

        for dt in my_dicts:
            test_document = dt

            print(f"\nAttempting to insert document with _id: {test_document['_id']}")
            insert_result = collection.insert_one(test_document)
            print(f"Insert successful! Inserted ID: {insert_result.inserted_id}")
            inserted_doc_id = insert_result.inserted_id


    except ConnectionFailure as e:
        print(f"\nError: Could not connect to MongoDB. Please check your MONGO_URI and network settings. Details: {e}")
    except OperationFailure as e:
        print(f"\nError: MongoDB operation failed. This might be due to authentication or permissions (e.g., user, database, collection permissions). Details: {e}")
    except PyMongoError as e:
        print(f"\nAn unexpected PyMongo error occurred: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during test operations: {e}")

    finally:
        if client:
            client.close()
            print("\nMongoDB client connection closed.")