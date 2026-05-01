#!/usr/bin/env python3
import os
import time
import io
import logging
import tempfile
import json
from datetime import datetime
from typing import List

import requests
from PIL import Image, ImageEnhance, ImageChops
import fitz  # PyMuPDF
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- Configuration (Defaults from Env) ---
KEY_FILE = "credentials.json"
CLOUD_NAME = os.getenv("CLOUD_NAME")
UPLOAD_PRESET = os.getenv("UPLOAD_PRESET")
UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"
AISENSY_API_KEY = os.getenv("AISENSY_API_KEY")
CAMPAIGN_NAME = os.getenv("AISENSY_CAMPAIGN_NAME")
TODAY = datetime.now().strftime("%d %B %Y")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def refresh_creds(creds: Credentials):
    if not creds.valid:
        creds.refresh(Request())

def get_sheet_gid(creds: Credentials, sheet_id: str, sheet_name: str) -> str:
    service = build("sheets", "v4", credentials=creds)
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    for sheet in meta["sheets"]:
        if sheet["properties"]["title"] == sheet_name:
            return str(sheet["properties"]["sheetId"])
    raise RuntimeError(f"Sheet '{sheet_name}' not found")

def crop_white_space(img: Image.Image) -> Image.Image:
    bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageEnhance.Contrast(ImageChops.difference(img, bg)).enhance(2.0)
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img

def optimize_image(img: Image.Image) -> bytes:
    if img.mode != "RGB": img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()

def run_automation(sheet_id: str, sheet_name: str, ranges: List[str], destinations: List[str]):
    logger.info(f"Starting automation for Sheet: {sheet_name} ({sheet_id})")
    
    # Auth
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    scopes = ["https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/spreadsheets.readonly"]
    if creds_json:
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(KEY_FILE, scopes=scopes)
    
    refresh_creds(creds)
    sheet_gid = get_sheet_gid(creds, sheet_id, sheet_name)
    
    uploaded_urls = []
    for i, r in enumerate(ranges, start=1):
        export_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
            f"?format=pdf&portrait=false&gid={sheet_gid}&range={r}"
            f"&size=A2&scale=3&top_margin=0.25&bottom_margin=0.25&left_margin=0.25&right_margin=0.25"
        )
        
        refresh_creds(creds)
        response = requests.get(export_url, headers={"Authorization": f"Bearer {creds.token}"}, timeout=60)
        response.raise_for_status()

        doc = fitz.open(stream=response.content, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = crop_white_space(img)

        jpg_data = optimize_image(img)
        
        # Upload
        upload = requests.post(UPLOAD_URL, files={"file": jpg_data}, data={
            "upload_preset": UPLOAD_PRESET,
            "folder": f"Automation_Exports/{datetime.now().strftime('%Y-%m-%d')}"
        })
        url = upload.json().get("secure_url")
        if url:
            uploaded_urls.append(url)
            logger.info(f"Uploaded range {r} -> {url}")

    # Send WhatsApp
    for dest in destinations:
        for i, url in enumerate(uploaded_urls, start=1):
            payload = {
                "apiKey": AISENSY_API_KEY,
                "campaignName": CAMPAIGN_NAME,
                "destination": dest,
                "userName": "Analytics Bot",
                "templateParams": [TODAY],
                "source": "automation-script",
                "media": {"url": url, "filename": f"report_{i}.jpg"}
            }
            requests.post("https://backend.aisensy.com/campaign/t1/api", json=payload, timeout=30)
            logger.info(f"Sent to {dest}")
            time.sleep(2)

if __name__ == "__main__":
    # For standalone run via Env Vars
    s_id = os.getenv("SHEET_ID")
    s_name = os.getenv("SHEET_NAME")
    s_ranges = os.getenv("RANGES", "").split(",")
    s_dests = os.getenv("DESTINATIONS", "").split(",")
    
    if s_id and s_name and s_ranges and s_dests:
        run_automation(s_id, s_name, s_ranges, s_dests)
    else:
        logger.error("Missing required parameters for Master Automation")
