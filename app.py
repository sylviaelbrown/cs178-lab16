"""
CS 178 - Lab 16: Serverless Image Processing with AWS Lambda + S3
app.py — Flask web server

This app lets a user upload an image through a web form.
Your job (Exercise 1): replace the two placeholder bucket name strings
below with your actual S3 bucket names.

Run locally:   python app.py  (port 8888)
Deployed via:  GitHub Actions → EC2 (same workflow as Lab 9)
"""

import boto3
import json
import time
import os
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# ── S3 Configuration ──────────────────────────────────────────────────────────
# TODO (Exercise 1): Replace these two placeholder strings with your actual
# bucket names — the ones you created in Section 1.
#
SOURCE_BUCKET    = "seb-image-source"           # e.g. "mkm-image-source"
PROCESSED_BUCKET = "seb-image-source-processed" # e.g. "mkm-image-source-processed"
AWS_REGION = "us-east-1"

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """
    Home page: shows the upload form.
    If a 'filename' query param is present (e.g. after a successful upload),
    it also fetches and displays the processed image from S3.
    """
    filename = request.args.get("filename")
    processed_url = None
    original_url = None
    rekognition_labels = None

    if filename:
        s3 = boto3.client("s3", region_name=AWS_REGION)

        # Pre-signed URL for the processed (flipped) image in the processed bucket
        processed_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": PROCESSED_BUCKET, "Key": filename},
            ExpiresIn=300,
        )

        # Pre-signed URL for the original image still in the source bucket
        original_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": SOURCE_BUCKET, "Key": filename},
            ExpiresIn=300,
        )

        # Try to fetch Rekognition labels if the stretch goal JSON file exists.
        # The rekognition Lambda writes a file named e.g. "dog.jpg_labels.json"
        # to the processed bucket. If it's not there, we just skip it gracefully.
        labels_key = f"{filename}_labels.json"
        try:
            labels_obj = s3.get_object(Bucket=PROCESSED_BUCKET, Key=labels_key)
            rekognition_labels = json.loads(labels_obj["Body"].read())
        except s3.exceptions.ClientError:
            pass  # Stretch goal not completed — that's fine

    return render_template(
        "index.html",
        processed_url=processed_url,
        original_url=original_url,
        rekognition_labels=rekognition_labels,
        filename=filename,
    )


@app.route("/upload", methods=["POST"])
def upload():
    """
    Handles the image upload form submission.

    Steps:
      1. Get the file from the form
      2. Upload it to SOURCE_BUCKET using boto3
      3. Wait briefly so Lambda has time to process it
      4. Redirect back to the home page with the filename so we can show the result
    """
    file = request.files.get("image")

    if not file or file.filename == "":
        return "No file selected.", 400

    filename = file.filename

    # ── Upload the file to S3 ─────────────────────────────────────────────────
    # boto3.client() creates a connection to the S3 service.
    # upload_fileobj() streams the file directly into the bucket —
    # 'file' is already a file-like object from Flask's request.files,
    # and 'filename' becomes the S3 key (the name the object gets in the bucket).
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.upload_fileobj(file, SOURCE_BUCKET, filename)
    # ─────────────────────────────────────────────────────────────────────────

    # Give Lambda ~3 seconds to process the image before we try to show it.
    # (In production you'd use an event/webhook instead of sleeping — but this
    #  is fine for a lab demo.)
    time.sleep(3)

    return redirect(url_for("index", filename=filename))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8888)