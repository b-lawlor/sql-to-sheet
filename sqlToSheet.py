import os
import psycopg2
import json
import base64
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import secretmanager

# environment variables should be set to the resource ids of your secrets in the global scope
# which can improve performance when Cloud Functions recyles its execution environment
client = secretmanager.SecretManagerServiceClient()
secret_response = client.access_secret_version(os.environ["III_SECRET"])
iii_secret = secret_response.payload.data.decode('UTF-8')
secret_response = client.access_secret_version(os.environ["SHEETS_SECRET"])
sheets_secret = json.loads(secret_response.payload.data.decode('UTF-8'))


def sqlToSheet(request):
    # set this as the Cloud Function's entry point
    # it expects a json payload in the form {"sql" : "base64 encoded SQL string", "sheet" : "SpreadsheetId" }
    # this is intended to be very flexible - append any sql results to any spreadsheet 
    request_json = requestHandler(request)

    if request_json and 'sql' in request_json and 'sheet' in request_json:
        sql = str(base64.b64decode(request_json['sql']), "utf-8")
        sheet = request_json['sheet']
        data = queryDb(sql)
        return appendToSheet(data, sheet)
    else:
        return "Error: malformed json payload" 


def requestHandler(request):
    # Cloud Functions request object is based on Flask
    request_json = request.get_json()

    # this handles Cloud Scheduler sending its JSON payload as octet-stream for no apaprent reason
    if not request_json and request.headers.get("Content-Type") == "application/octet-stream":
        string_request_data = request.data.decode("utf-8")
        request_json: dict = json.loads(string_request_data)

    if request_json:
        return request_json
    else:
        return "500" # error code is obviously up to you


def queryDb(sql):
    # connect to Sierra db and run SQL query
    conn = psycopg2.connect(iii_secret)
    cursor = conn.cursor()
    cursor.execute(sql)
    data = cursor.fetchall()
    conn.close()

    return data


def appendToSheet(data, spreadSheetId):
    # appends 2d array to the specified sheet, byo spreadsheet and service account
    # the service account will need to have edit rights and a sheet named 'data'
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_info(sheets_secret, scopes=scopes)
    service = build('sheets', 'v4', credentials=creds)

    request = service.spreadsheets().values().append(
        spreadsheetId=spreadSheetId, range='data!A1:Z1',
        valueInputOption='USER_ENTERED' ,body={'values': data})
    return request.execute()
