import json
import logging
from os.path import join, dirname, exists
import requests
from fastapi import (
    FastAPI,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Body,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from letta import create_client
# from utils import say
import uvicorn
from dotenv import load_dotenv
import io
from PyPDF2 import PdfReader
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
import pytz
from typing import Optional, Set
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from pydantic import BaseModel, HttpUrl
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
from starlette.websockets import WebSocket
from starlette.types import Scope
import ast

from create_agent import TaskMemory

# Function to extract cookies manually (if needed)
def get_cookie(scope: Scope, key: str):
    cookies = {}
    for header in scope.get("headers", []):
        if header[0].decode().lower() == "cookie":
            cookie_str = header[1].decode()
            for cookie in cookie_str.split("; "):
                if "=" in cookie:
                    k, v = cookie.split("=", 1)
                    cookies[k] = v
    return cookies.get(key)

# Load environment variables
# dotenv_path = join(dirname(__file__), '.env')
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO or WARNING in production
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Initialize the scheduler
scheduler = BackgroundScheduler(timezone="Asia/Hong_Kong")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend's URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
app.mount("/static", StaticFiles(directory="../frontend/build/static"), name="static")
app.mount("/img", StaticFiles(directory="../frontend/public/img"), name="img")

# Spotify Configuration
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# Initialize MemGPT client and attach to agent
client = create_client()

# Pydantic model for User
class User(BaseModel):
    username: str
    email: str

def get_current_user():
    return User(username="Good Guy", email="goodguy@good.com")

def get_existing_agent(agent_name: str):
    agents = client.list_agents()
    for agent in agents:
        logger.debug(f"Agent {agent.id} is named {agent.name}")
        if agent.name == agent_name:
            return agent
    return None

def get_existing_source(data_source_name: str):
    data_sources = client.list_sources()
    for data_source in data_sources:
        logger.debug(f"Source {data_source.id} is named {data_source.name}")
        if data_source.name == data_source_name:
            return data_source
    return None

# Connect to the existing agent and source
agent_name = "PG Copilot"  # Replace with your agent's name
data_source_name = "pg-copilot-Data"  # Replace with your data source's name

agent_state = get_existing_agent(agent_name)

if not agent_state:
    logger.error(f"No agent with the name '{agent_name}' was found. Please create it manually.")
    exit(1)

print(f"Agent found: {agent_state.name} with ID {str(agent_state.id)}")

source_state = get_existing_source(data_source_name)

if not source_state:
    logger.info(f"No source named '{data_source_name}' found. Creating it now.")
    client.create_source(name=data_source_name)
    source_state = get_existing_source(data_source_name)
    if not source_state:
        logger.error("Source was created but could not be found. Please try again.")
        exit(1)

attached_list = client.list_attached_sources(agent_id=agent_state.id)

if source_state.id in [attached_source.id for attached_source in attached_list]:
    logger.info(f"Source '{data_source_name}' is already attached to agent '{agent_name}'.")
else:
    print(f"Start Attached source '{data_source_name}' {source_state.id} to agent '{agent_name}'.")
    logger.info(f"Start Attached source '{data_source_name}' to agent '{agent_name}'.")
    client.attach_source_to_agent(agent_id=agent_state.id, source_id=source_state.id)
    logger.info(f"Finished Attached source '{data_source_name}' to agent '{agent_name}'.")

# Store active WebSocket connections
active_connections: Set[WebSocket] = set()

# WebSocket Endpoints
import ast

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # !! bypass authentication for now
    # app_access_token = get_cookie(websocket.scope, "app_access_token")
    # if not app_access_token:
    #     logger.warning("WebSocket connection attempted without token.")
    #     await websocket.close(code=1008)  # Policy Violation
    #     return
    # try:
    #     user = get_current_user()
    #     username = user.username
    #     logger.info(f"WebSocket connection accepted for user: {username}")
    # except HTTPException as e:
    #     logger.warning(f"WebSocket connection closed due to invalid token: {e.detail}")
    #     await websocket.close(code=1008)
    #     return
    user = get_current_user()
    username = user.username
    active_connections.add(websocket)
    logger.info(f"WebSocket connection established for user: {username}")
    print(f"WebSocket connection established for user: {username}")

    try:
        while True:
            pre_function_name = "none"
            try:
                # Receive the incoming message
                data = await websocket.receive_text()
                message = json.loads(data)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected by {username}.")
                break
            except Exception as e:
                logger.error(f"Error receiving message from {username}: {e}")
                await websocket.send_json({"error": "Invalid message format."})
                continue

            try:
                command = message.get('message', '')
                logger.debug(f"Processing command from {username}: {command}")
                print(f"Processing command from {username}: {command}")

                if command:

                    response = client.user_message(agent_id=agent_state.id, message=command)
                    print(f"Response from agent: {response}")

                    # Loop through all the messages in the response
                    for r in response.messages:
                        # Handle thought messages
                        message_type = ""
                        if hasattr(r, 'message_type'):
                            message_type = r.message_type
                        if message_type == "internal_monologue":
                            thought_message = {
                                "type": "thought",
                                "message": r.internal_monologue
                            }

                            await websocket.send_json(thought_message)
                            logger.debug(f"Sent thought message to {username}: {thought_message}")

                        elif message_type == "function_call":
                            function_call = r.function_call
                            function_name = function_call.name

                            arguments_str = function_call.arguments
                            if function_name == "send_message":
                                content = json.loads(arguments_str)
                                agent_message = {
                                    "type": "message",
                                    "message": content['message']
                                }
                                await websocket.send_json(agent_message)
                                logger.debug(f"Sent thought message to {username}: {thought_message}")
                            else:
                                function_call_message = {
                                    "type": "function_call",
                                    "message": f"Function: {function_name} called with arguments: {arguments_str}"
                                }
                                print(function_name)
                                pre_function_name = function_name
                                await websocket.send_json(function_call_message)
                                logger.debug(f"Sent function call to {username}: {function_call_message}")

                        elif message_type == "function_return":
                            function_return = r.function_return
                            function_return_message = {
                                "type": "function_return",
                                "message": function_return
                            }
                            if pre_function_name=="analyze_project" or pre_function_name=="pdf_translate":
                                #
                                # print(function_return['message'])
                                await websocket.send_text(function_return)
                                #await websocket.send(function_return)
                                pre_function_name="none"
                            else:
                                await websocket.send_json(function_return_message)
                            logger.debug(f"Sent function return to {username}: {function_return_message}")

                        else:
                            logger.warning(f"Unhandled message type: {message_type}")

            except Exception as e:
                logger.error(f"Error processing message from {username}: {e}")
                await websocket.send_text(f"Error: {str(e)}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected gracefully by {username}.")
    finally:
        active_connections.remove(websocket)
        await broadcast_log(f"WebSocket connection closed for {username}.")

# Function to broadcast log messages to all active WebSocket connections
async def broadcast_log(log: str):
    for connection in active_connections:
        try:
            await connection.send_json({"LOG": log})
        except Exception as e:
            logger.error(f"Error broadcasting log to WebSocket: {e}")

# Function to broadcast messages to all active WebSocket connections
async def broadcast_message(message: str):
    for connection in active_connections:
        try:
            await connection.send_json({"message": message})
            logger.debug(f"Broadcasted message to WebSocket: {message}")
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")

# File Upload Endpoint
@app.post("/upload")
async def upload_file(file: UploadFile):
    try:
        content = await file.read()
        filename = file.filename
        logger.info(f"Received file: {filename}")

        # Try to decode as UTF-8, fall back to handling as binary if it fails
        try:
            content_str = content.decode("utf-8")  # Decode the bytes to a string
            logger.info(f"File {filename} decoded as UTF-8")

            # Check if the file is a code file and process it
            if filename.endswith(('.py', '.js', '.java', '.html', '.css', '.cpp', '.ts')):
                logger.info(f"Processing code file: {filename}")
                client.insert_archival_memory(agent_state.id, content_str)
            else:
                logger.info(f"File {filename} is not a code file, handling as text.")
                client.insert_archival_memory(agent_state.id, content_str)

        except UnicodeDecodeError:
            logger.warning(f"File {filename} could not be decoded as UTF-8, handling as binary.")

            # Handle binary files (PDFs)
            if filename.endswith(".pdf"):
                try:
                    pdf_file = io.BytesIO(content)  # Convert bytes to a file-like object
                    reader = PdfReader(pdf_file)
                    extracted_text = ""
                    
                    # Extract text from all the pages
                    for page in reader.pages:
                        extracted_text += page.extract_text()

                    # Insert extracted text into memory
                    client.insert_archival_memory(agent_state.id, extracted_text)
                    logger.info(f"Extracted text from {filename} and added to archival memory.")
                except Exception as e:
                    logger.error(f"Error processing PDF {filename}: {e}")
                    return {"message": f"Error processing PDF {filename}: {e}"}
            else:
                logger.warning(f"Binary file {filename} is not a supported type.")
                return {"message": f"Binary file {filename} is not a supported type."}

    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {e}")
        return {"message": f"Error processing file {file.filename}: {e}"}

    return {"message": f"Successfully processed {filename}"}

# Function to fetch Google Calendar events
def fetch_google_calendar_events():
    TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'gcal_token.json')
    CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api', 'google_api_credentials.json')
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    
    # Load credentials
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    service = build('calendar', 'v3', credentials=creds)

    # Define the Hong Kong time zone
    hk_tz = pytz.timezone('Asia/Hong_Kong')

    # Get the current time in the Hong Kong time zone
    now = datetime.now(hk_tz)

    # Format the current time as an RFC3339 string
    now_rfc3339 = now.isoformat()

    # Call the Calendar API to fetch events in Hong Kong time zone
    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now_rfc3339,  # Ensure this is in RFC3339 format
            timeZone='Asia/Hong_Kong',  # Specify the time zone for the query
            maxResults=5,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        logger.info(f"Fetched {len(events)} calendar events.")
        return events

    except HttpError as error:
        logger.error(f"An error occurred while fetching calendar events: {error}")
        return []

# Calendar Events Endpoint
@app.get("/api/calendar-events")
def get_calendar_events():
    events = fetch_google_calendar_events()
    return events

# Initialize the tasks.json file
def initialize_tasks_file():
    # Check if tasks.json exists and is not empty
    if not exists('tasks.json'):
        # If the file doesn't exist, create it with an empty list
        with open('tasks.json', 'w') as f:
            json.dump([], f)  # Initialize with an empty list
            logger.info("Initialized tasks.json with an empty list.")

# Load tasks from tasks.json or initialize an empty list if file doesn't exist
if os.path.exists('tasks.json'):
    with open('tasks.json', 'r') as f:
        try:
            tasks = json.load(f)
            logger.info(f"Loaded {len(tasks)} tasks from tasks.json.")
        except json.JSONDecodeError:
            tasks = []
            logger.warning("tasks.json is corrupted. Initialized with an empty list.")
else:
    initialize_tasks_file()
    tasks = []

# Tasks Endpoints
@app.get("/api/tasks")
def get_tasks():
    
    if not exists('./tasks.json'):
        logger.info("tasks.json does not exist. Returning empty task list.")
        return {"tasks": []}  # Return empty list if file doesn't exist

    with open('./tasks.json', 'r') as f:
        try:
            tasks = json.load(f)
            if not isinstance(tasks, list):
                tasks = [tasks]
            logger.info(f"Tasks loaded from JSON: {tasks}")
        except json.JSONDecodeError:
            tasks = []
            logger.warning("tasks.json is corrupted. Returning empty task list.")
    
    return {"tasks": tasks}

@app.post("/api/tasks/add")
async def add_task(task: dict = Body(...)):
    user = get_current_user()
    task_description = task.get("task")
    if not task_description:
        logger.warning(f"Empty task received from user: {user.username}")
        raise HTTPException(status_code=400, detail="Task description is required.")
    
    # Push task to agent memory and save it
    # ?? the custom memory function is overridden in save_agent(agent, self.ms) in create_agent in sync server
    '''print("agent_state.memory before")
    print(agent_state.memory)
    agent_state.memory.task_queue_push(task_description)   
    tasks_tmp = json.loads(self.memory.get_block("tasks").value)
    tasks_tmp.append(task_description)
    self.memory.update_block_value("tasks", json.dumps(tasks))
    print("agent_state.memory after")
    print(agent_state.memory) '''
    
    tasks = json.loads(agent_state.memory.get_block("tasks").value)
    #tasks.append(task_description)
    agent_state.memory.update_block_value("tasks", json.dumps(tasks))
    # write to tasks.json
    '''with open('./tasks.json', 'w') as f:
        json.dump(tasks, f)'''
    logger.info(f"Task added by {user.username}: {task_description}")
    return {"tasks": tasks}

# Text-to-Speech Playback Endpoint
@app.get("/api/play-tts", response_class=FileResponse)
def play_tts():
    user = get_current_user()
    
    # Define the path to the latest generated TTS MP3 file
    file_path = "output.mp3"  # Replace with your actual path if necessary

    if os.path.exists(file_path):
        logger.info(f"Playing TTS file: {file_path}")
        return FileResponse(file_path, media_type="audio/mpeg", filename="output.mp3")
    else:
        logger.warning(f"TTS file not found: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")

# Spotify Helper Functions
def set_spotify_volume(spotify_token: str, device_id: str, volume_percent: int):
    headers = {
        "Authorization": f"Bearer {spotify_token}",
        "Content-Type": "application/json"
    }

    # Spotify API endpoint to set volume
    volume_url = "https://api.spotify.com/v1/me/player/volume"
    params = {
        "volume_percent": volume_percent,  # Volume level from 0 to 100
        "device_id": device_id  # Specify the device ID
    }

    volume_response = requests.put(volume_url, headers=headers, params=params)

    if volume_response.status_code == 204:
        logger.info(f"Volume set to {volume_percent}% on device {device_id}.")
    else:
        logger.error(f"Error setting volume: {volume_response.status_code}, {volume_response.text}")

def play_spotify_alarm(spotify_token: str, playlist_uri: str, track_uri: Optional[str] = None, volume_percent: int = 100):
    headers = {
        "Authorization": f"Bearer {spotify_token}",
        "Content-Type": "application/json"
    }

    # Get available devices
    devices_response = requests.get("https://api.spotify.com/v1/me/player/devices", headers=headers)

    if devices_response.status_code == 200:
        devices = devices_response.json()["devices"]
        if not devices:
            logger.warning("No active Spotify devices found.")
            return
        else:
            # Check for a device named "Jarvis"
            jarvis_device = next((device for device in devices if device['name'] == 'Jarvis'), None)
            if jarvis_device:
                device_id = jarvis_device['id']
                logger.info(f"Using device: {jarvis_device['name']}")
            else:
                logger.info("Device named 'Jarvis' not found. Using the first available device.")
                device_id = devices[0]['id']  # Default to the first device if "Jarvis" is not found
    else:
        logger.error(f"Error fetching Spotify devices: {devices_response.status_code}, {devices_response.text}")
        return

    # Set the volume before starting playback
    set_spotify_volume(spotify_token, device_id, volume_percent)

    # Prepare the data for playback
    play_data = {
        "context_uri": playlist_uri  # Ensure the context is the playlist so it continues playing the rest
    }

    # Optionally add an offset to start from a specific track in the playlist
    if track_uri:
        play_data["offset"] = {"uri": track_uri}  # Start from this track, but continue with the playlist

    # Now, start playback on the specified device
    play_url = "https://api.spotify.com/v1/me/player/play"
    play_response = requests.put(play_url, headers=headers, json=play_data, params={"device_id": device_id})

    if play_response.status_code == 204:
        device_name = jarvis_device['name'] if jarvis_device else devices[0]['name']
        logger.info(f"Started playing on device {device_name}.")
    else:
        logger.error(f"Error starting playback: {play_response.status_code}, {play_response.text}")

# Wakeup Message Functions
async def send_wakeup_message():
    current_time = datetime.now().strftime("%H:%M:%S")
    message = f"Good morning! The time is {current_time}. Let's start the day!"
    await broadcast_message(message=message)  # Send the message over WebSocket
    # say(message)  # Use the TTS function to speak the message
    logger.info("Woke up user with message.")

def send_wakeup_message_wrapper():
    asyncio.run(send_wakeup_message())  # Run the async function in a synchronous context

# Schedule the wakeup message at 7:00 AM
scheduler.start()
scheduler.add_job(send_wakeup_message_wrapper, 'cron', hour=7, minute=0)
logger.info("Scheduler started and wakeup message scheduled at 7:00 AM daily.")

# WebSocket Broadcast Function
async def broadcast_message(message: str):
    for connection in active_connections:
        try:
            await connection.send_json({"message": message})
            logger.debug(f"Broadcasted message to WebSocket: {message}")
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")

@app.get("/frontend")
def serve_frontend():
    index_file_path = "../frontend/build/index.html"
    if os.path.exists(index_file_path):
        return FileResponse(index_file_path)
    else:
        return {"error": "index.html not found"}

@app.get("/")
def serve_frontend_root():
    index_file_path = "../frontend/build/index.html"
    if os.path.exists(index_file_path):
        return FileResponse(index_file_path)
    else:
        return {"error": "index.html not found"}

# Run the application
if __name__ == '__main__':
    import uvicorn
    logger.info("Starting the application.")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
    logger.info("Application stopped.")
