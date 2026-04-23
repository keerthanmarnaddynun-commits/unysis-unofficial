# app.py

from flask import Flask, request, jsonify
import os

# Import your modules
from utils.metadata import create_metadata
from utils.legal import generate_legal_notice

from flask_cors import CORS


# Create Flask app
app = Flask(__name__)
CORS(app)

# Folder to temporarily store uploaded files
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def dummy_predict(file_path):
    """
    TEMPORARY prediction function.
    This will be replaced by the real model later (Role 2).

    Returns:
    - result: "Real" or "Fake"
    - confidence: float
    """
    # For now, always return Fake for testing
    return "Fake", 0.85


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Main API endpoint:
    - Receives file
    - Runs prediction
    - Generates metadata
    - Generates legal notice (if needed)
    - Returns structured response
    """

    # Check if file is present in request
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    # Check if filename is empty
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    # Validate file size (max 500MB)
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({"error": f"File too large. Maximum size: 500MB, received: {file_size / 1024 / 1024:.2f}MB"}), 413
    
    if file_size == 0:
        return jsonify({"error": "Empty file"}), 400

    # Save file to uploads folder
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    try:
        file.save(file_path)
    except Exception as e:
        return jsonify({"error": f"Failed to save file: {str(e)}"}), 500

    try:
        # --- Step 1: Prediction (currently dummy) ---
        result, confidence = dummy_predict(file_path)

        # --- Step 2: Metadata ---
        metadata = create_metadata(file_path, result, confidence)

        # --- Step 3: Legal Notice ---
        notice = generate_legal_notice(metadata)

        # Add legal notice to response
        metadata["legal_notice"] = notice if notice else ""

        # Return final JSON response
        return jsonify(metadata)
    
    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500
    
    finally:
        # Clean up uploaded file after processing
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass


# Run the app
if __name__ == "__main__":
    app.run(debug=False, port=5000)