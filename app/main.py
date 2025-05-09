#!/usr/bin/env python3

import logging.handlers
import subprocess
import asyncio
import sys
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, List, Any, Optional

# Import the settings module
from app import settings

# Configure console logging
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Create logger
logger = logging.getLogger("camera_downloader")
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

app = FastAPI()

# Helper function to check if camera is reachable
def is_camera_reachable(ip: str) -> tuple[bool, str]:
    """Check if a camera is reachable at the specified IP address
    
    Args:
        ip: IP address to ping
        
    Returns:
        Tuple of (is_reachable, message)
    """
    logger.debug(f"Pinging camera at {ip}")
    try:
        # Run ping command with 2 second timeout, 3 packets
        result = subprocess.run(
            ["ping", "-c", "3", "-W", "2", ip],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"Camera at {ip} is reachable")
            return True, f"Camera at {ip} is reachable"
        else:
            logger.warning(f"Camera at {ip} is not reachable")
            return False, f"Camera at {ip} is not reachable"
    except Exception as e:
        logger.error(f"Error pinging camera: {str(e)}")
        return False, f"Error pinging camera: {str(e)}"

@app.get("/camera/ping")
async def ping_camera(ip: str) -> Dict[str, Any]:
    """Ping a camera at specified IP address"""
    logger.info(f"Ping request received for camera at {ip}")
    is_reachable, message = is_camera_reachable(ip)
    return {"success": is_reachable, "message": message}

@app.get("/camera/save-settings")
async def save_camera_settings(type: str, ip: str) -> Dict[str, Any]:
    """Save camera settings to persistent storage"""
    logger.info(f"Saving camera settings: type={type}, ip={ip}")
    success = settings.update_camera_ip(type, ip)
    
    if success:
        return {"success": True, "message": f"Camera settings saved for {type}"}
    else:
        return {"success": False, "message": "Failed to save camera settings"}

@app.get("/camera/get-settings")
async def get_camera_settings() -> Dict[str, Any]:
    """Get saved camera settings"""
    logger.info("Getting camera settings")
    
    try:
        # Get the last used camera settings
        last_used = settings.get_last_used()
        
        # Get IP addresses for both camera types
        siyi_ip = settings.get_camera_ip('siyi')
        xfrobot_ip = settings.get_camera_ip('xfrobot')
        
        return {
            "success": True,
            "last_used": last_used,
            "cameras": {
                "siyi": {"ip": siyi_ip},
                "xfrobot": {"ip": xfrobot_ip}
            }
        }
    except Exception as e:
        logger.exception(f"Error getting camera settings: {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}

async def download_generator(type: str, ip: str):
    """Generator function for streaming download progress"""
    logger.info(f"Download request received for {type} camera at {ip}")
    
    # Save the camera settings when a download is requested
    settings.update_camera_ip(type, ip)
    
    # Correct SSE format with "data:" prefix and double newline
    yield f"data: Connecting to camera at {ip}\n\n"

    try:
        # check if camera is reachable
        is_reachable, message = is_camera_reachable(ip)
        if not is_reachable:
            logger.warning(f"Camera at {ip} is not reachable, aborting download")
            yield f"data: Error: {message}. Please check the connection and try again\n\n"
            return

        # Set up download directory
        current_dir = Path.cwd()
        downloads_dir = current_dir / "downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)

        # Get script path
        script_dir = Path(__file__).parent
        script_path = script_dir / f"{type}-download.py"

        if not script_path.exists():
            logger.error(f"Download script {script_path} not found")
            yield f"data: Error: download script for {type} camera not found\n\n"
            return

        # Build command
        cmd = f"python3 {script_path} --ipaddr {ip} --dest {downloads_dir}"

        # display download started message
        yield f"data: Started download from {type} camera at {ip}\n\n"
        yield f"data: This may take a while depending on the number of files...\n\n"
        yield f"data: Files will be saved to: {downloads_dir}\n\n"

        # Execute command
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Set up heartbeat task
        heartbeat_interval = 5  # seconds
        last_message_time = asyncio.get_event_loop().time()
        
        # Process stdout in real-time
        while True:
            try:
                # set a timeout to send heartbeats if case no lines received
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=heartbeat_interval
                )

                # process incoming lines
                if line:
                    line_text = line.decode('utf-8').rstrip()
                    logger.debug(f"Script output: {line_text}")
                    yield f"data: {line_text}\n\n"
                    last_message_time = asyncio.get_event_loop().time()
                else:
                    # end of output
                    break

            except asyncio.TimeoutError:
                # send heartbeat
                current_time = asyncio.get_event_loop().time()
                if current_time - last_message_time >= heartbeat_interval:
                    logger.debug("Sending heartbeat to keep connection alive")
                    # Heartbeat in correct SSE format
                    yield ":\n\n"
                    last_message_time = current_time
                    
                # check if process is still running
                if process.returncode is not None:
                    break

        # Wait for process to complete
        await process.wait()

        # Check result
        if process.returncode == 0:
            yield "data: Download completed successfully!\n\n"
            yield f"data: Files have been downloaded to: {downloads_dir}\n\n"
        else:
            error = await process.stderr.read()
            error_text = error.decode('utf-8')
            yield f"data: Download failed with Error: {error_text}\n\n"

    except Exception as e:
        logger.exception(f"Error in download process: {str(e)}")
        yield f"data: Error during download: {str(e)}\n\n"
        
    # Final heartbeat before closing
    yield ":\n\n"

@app.get("/camera/download")
async def download_images(type: str, ip: str):
    """Download images from camera based on type and IP address"""
    return StreamingResponse(
        download_generator(type, ip),
        media_type="text/event-stream"
    )

# Mount static files AFTER defining API routes
# Use absolute path to handle Docker container environment
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

# Set up logging for the app
log_dir = Path('app/logs')
log_dir.mkdir(parents=True, exist_ok=True)
fh = logging.handlers.RotatingFileHandler(log_dir / 'lumber.log', maxBytes=2**16, backupCount=1)
logger.addHandler(fh)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
