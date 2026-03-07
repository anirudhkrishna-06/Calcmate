import os
import sys
from PIL import Image
import cv2
import numpy as np
import pytesseract
import easyocr
import threading

# Configuration
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Global EasyOCR Reader (Lazy loaded)
_EASYOCR_READER = None
_READER_LOCK = threading.Lock()

def get_easyocr_reader():
    """
    Get or initialize the global EasyOCR reader in a thread-safe manner.
    """
    global _EASYOCR_READER
    with _READER_LOCK:
        if _EASYOCR_READER is None:
            print("🚀 Initializing EasyOCR Reader (this may take a moment)...")
            # gpu=True if available, else False. model_storage_directory can be added if needed.
            _EASYOCR_READER = easyocr.Reader(['en'], gpu=True)
            print("✅ EasyOCR Reader initialized.")
    return _EASYOCR_READER

def preprocess_image(img_path):
    """
    Convert image to grayscale, denoise, and apply threshold.
    Returns a PIL Image.
    """
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"Image not found: {img_path}")

    img = cv2.imread(img_path)
    if img is None:
        raise ValueError(f"Could not read image using cv2: {img_path}")

    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Thresholding (OTSU is usually good for text)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Return as PIL Image
    return Image.fromarray(thresh)

# --- Run Tesseract OCR ---
def run_tesseract(img):
    """
    Run Tesseract OCR on a PIL Image.
    """
    try:
        # psm 6 = Assume a single uniform block of text.
        text = pytesseract.image_to_string(img, config="--oem 3 --psm 6")
        return text.strip()
    except Exception as e:
        print(f"⚠️ Tesseract failed: {e}")
        return ""

# --- Run EasyOCR ---
def run_easyocr(img_path):
    """
    Run EasyOCR using the global reader instance.
    """
    try:
        reader = get_easyocr_reader()
        # detail=0 returns just the list of text strings
        results = reader.readtext(img_path, detail=0)
        text = " ".join(results)
        return text.strip()
    except Exception as e:
        print(f"⚠️ EasyOCR failed: {e}")
        return ""

# --- Fuse results ---
def fuse_text(tess_text, easy_text):
    """
    Simple fusion strategy: prefers the longer text as it likely contains more information,
    unless one is empty.
    """
    tess_text = tess_text.strip()
    easy_text = easy_text.strip()

    if not tess_text and not easy_text:
        return ""
    
    # Heuristic: Trust EasyOCR more for clarity but Tesseract sometimes gets structure better.
    # For now, length is a reasonable proxy for "amount of content captured".
    if len(easy_text) > len(tess_text):
        return easy_text
    return tess_text

# --- Process single image ---
def process_image(img_path):
    """
    Main entry point for OCR. 
    1. Preprocesses image
    2. Runs Tesseract
    3. Runs EasyOCR
    4. Fuses results
    """
    try:
        # Preprocess for Tesseract (it benefits more from clean binary images)
        preprocessed_img = preprocess_image(img_path)
        tess_text = run_tesseract(preprocessed_img)

        # EasyOCR handles raw images well, often better than thresholded ones
        easy_text = run_easyocr(img_path)

        fused = fuse_text(tess_text, easy_text)
        
        # Optional debug print - can be removed for production to reduce log noise
        # print(f"DEBUG [OCR]: Tess='{tess_text[:20]}...', Easy='{easy_text[:20]}...' -> Fused='{fused[:20]}...'")
        
        return fused
    except Exception as e:
        print(f"❌ Error processing image {img_path}: {e}")
        return ""

# --- Process folder ---
def process_folder(folder_path, save_results=False, output_folder="ocr_results"):
    if not os.path.exists(folder_path):
        print(f"ERROR: Folder not found: {folder_path}")
        return

    if save_results:
        os.makedirs(output_folder, exist_ok=True)

    supported_ext = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")
    images = [f for f in os.listdir(folder_path) if f.lower().endswith(supported_ext)]
    
    if not images:
        print(f"No images found in folder: {folder_path}")
        return

    print(f"Processing {len(images)} images in {folder_path}...")
    
    # Pre-initialize reader
    get_easyocr_reader()

    for img_file in images:
        img_path = os.path.join(folder_path, img_file)
        fused_text = process_image(img_path)
        
        print(f"Processed {img_file}: {fused_text[:50]}...")
        
        if save_results:
            out_path = os.path.join(output_folder, os.path.splitext(img_file)[0] + ".txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(fused_text)
                
    print("\n✅ All images processed.")

if __name__ == "__main__":
    # Simple CLI test
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        # Default test path if none provided
        path = r"mathq.jpeg" 

    if os.path.exists(path):
        if os.path.isfile(path):
            print(f"Result: {process_image(path)}")
        else:
            process_folder(path)
    else:
        print(f"Path not found: {path}")