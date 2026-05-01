#!/usr/bin/env python3

import os
import time
import io
import logging
import tempfile
from datetime import datetime
from typing import List

import requests
from PIL import Image, ImageEnhance, ImageChops
from pdf2image import convert_from_bytes
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

KEY_FILE = "credentials.json"

SHEET_ID = os.getenv("SHEET_ID")
SHEET_NAME = "Whatsapp"

RANGES = [
    f"{SHEET_NAME}!A2:M19",
]

CLOUD_NAME = os.getenv("CLOUD_NAME")
UPLOAD_PRESET = os.getenv("UPLOAD_PRESET")
UPLOAD_URL = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

AISENSY_API_KEY = os.getenv("AISENSY_API_KEY")
CAMPAIGN_NAME = os.getenv("AISENSY_CAMPAIGN_NAME")
DESTINATIONS = [d.strip() for d in os.getenv("DESTINATIONS", "").split(",") if d.strip()]

TODAY = datetime.now().strftime("%d %B %Y")

TARGET_SIZE_BYTES = 4 * 1024 * 1024
JPEG_QUALITIES = [95, 85, 75, 65, 55, 45]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def refresh_creds(creds: Credentials):
    if not creds.valid:
        creds.refresh(Request())
        logger.info("Google service account token refreshed.")


def get_sheet_gid(creds: Credentials, sheet_name: str) -> str:
    service = build("sheets", "v4", credentials=creds)
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()

    for sheet in meta["sheets"]:
        props = sheet["properties"]
        if props["title"] == sheet_name:
            return str(props["sheetId"])

    raise RuntimeError(f"Sheet '{sheet_name}' not found")


def jpg_bytes(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def optimize_image(img: Image.Image) -> bytes:
    if img.mode != "RGB":
        img = img.convert("RGB")

    for q in JPEG_QUALITIES:
        data = jpg_bytes(img, q)
        logger.info("Quality %d → %.2f MB", q, len(data) / 1024 / 1024)
        if len(data) <= TARGET_SIZE_BYTES:
            return data

    w, h = img.size
    for _ in range(3):
        w = int(w * 0.97)
        h = int(h * 0.97)
        img = img.resize((w, h), Image.LANCZOS)
        data = jpg_bytes(img, 55)
        if len(data) <= TARGET_SIZE_BYTES:
            return data

    return data


def crop_white_space(img: Image.Image) -> Image.Image:
    bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageEnhance.Contrast(ImageChops.difference(img, bg)).enhance(2.0)
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img


def export_and_upload_images() -> List[str]:
    creds = Credentials.from_service_account_file(
        KEY_FILE,
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/spreadsheets.readonly",
        ],
    )

    refresh_creds(creds)

    sheet_gid = get_sheet_gid(creds, SHEET_NAME)
    logger.info("Using sheet '%s' with gid=%s", SHEET_NAME, sheet_gid)

    drive = build("drive", "v3", credentials=creds)
    drive.files().get(fileId=SHEET_ID, fields="name").execute()

    uploaded_urls = []

    for i, sheet_range in enumerate(RANGES, start=1):
        range_only = sheet_range.split("!")[1]

        export_url = (
            f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export"
            f"?format=pdf"
            f"&portrait=false"
            f"&gid={sheet_gid}"
            f"&range={range_only}"
            f"&size=A2"
            f"&scale=3"
            f"&top_margin=0.25"
            f"&bottom_margin=0.25"
            f"&left_margin=0.25"
            f"&right_margin=0.25"
        )

        logger.info("Downloading %s", sheet_range)

        refresh_creds(creds)
        response = requests.get(
            export_url,
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=60,
        )
        response.raise_for_status()

        pages = convert_from_bytes(response.content, dpi=600)
        img = pages[0].convert("RGB")
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = crop_white_space(img)

        jpg_data = optimize_image(img)

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_table_{i}.jpg") as tmp:
            tmp.write(jpg_data)
            filename = tmp.name

        try:
            with open(filename, "rb") as f:
                upload = requests.post(
                    UPLOAD_URL,
                    files={"file": f},
                    data={
                        "upload_preset": UPLOAD_PRESET,
                        "folder": f"BizCat_Exports/{datetime.now().strftime('%Y-%m-%d')}",
                    },
                    timeout=60,
                )
                upload.raise_for_status()

            url = upload.json().get("secure_url")
            if url:
                uploaded_urls.append(url)
                logger.info("Uploaded → %s", url)
        finally:
            os.remove(filename)

        time.sleep(2)

    return uploaded_urls


def send_via_aisensy(urls: List[str]):
    if not urls:
        logger.warning("No images generated, skipping WhatsApp.")
        return

    for dest in DESTINATIONS:
        for i, url in enumerate(urls, start=1):
            payload = {
                "apiKey": AISENSY_API_KEY,
                "campaignName": CAMPAIGN_NAME,
                "destination": dest,
                "userName": "PW Online- Analytics",
                "templateParams": [TODAY],
                "source": "automation-script",
                "media": {"url": url, "filename": f"table_{i}.jpg"},
            }

            r = requests.post(
                "https://backend.aisensy.com/campaign/t1/api",
                json=payload,
                timeout=30,
            )
            logger.info("Sent to %s → status %s", dest, r.status_code)
            time.sleep(5)


if __name__ == "__main__":
    required = [
        "SHEET_ID",
        "CLOUD_NAME",
        "UPLOAD_PRESET",
        "AISENSY_API_KEY",
        "DESTINATIONS",
    ]

    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"Missing secrets: {', '.join(missing)}")

    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError("credentials.json not found")

    Image.MAX_IMAGE_PIXELS = 500_000_000

    urls = export_and_upload_images()
    send_via_aisensy(urls)
    logger.info("Automation completed successfully.")

