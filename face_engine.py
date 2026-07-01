import os
import urllib.request
import cv2
import numpy as np

# Directory to store the ONNX models
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

YUNET_MODEL_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_MODEL_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

def download_model(url, save_path):
    if not os.path.exists(save_path):
        print(f"Downloading model from {url} to {save_path}...")
        try:
            # Add a user-agent to avoid HTTP 403 Forbidden errors
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req) as response, open(save_path, 'wb') as out_file:
                out_file.write(response.read())
            print("Download completed successfully.")
        except Exception as e:
            print(f"Failed to download model: {e}")
            raise e

# Auto-download models when face_engine is imported/initialized
def init_models():
    download_model(YUNET_URL, YUNET_MODEL_PATH)
    download_model(SFACE_URL, SFACE_MODEL_PATH)

class FaceEngine:
    def __init__(self):
        init_models()
        self.detector = None
        self.recognizer = None
        
        # Load the models using OpenCV DNN
        try:
            # We initialize detector with dummy size, will update during detection
            self.detector = cv2.FaceDetectorYN.create(
                YUNET_MODEL_PATH,
                "",
                (320, 320),
                0.9,
                0.3,
                5000
            )
            self.recognizer = cv2.FaceRecognizerSF.create(
                SFACE_MODEL_PATH,
                ""
            )
        except Exception as e:
            print(f"Error loading face models: {e}")

    def get_embedding(self, image_bytes: bytes):
        """
        Processes image bytes, detects the primary face, aligns/crops it, and extracts the embedding.
        """
        # Decode image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None, "Invalid image format"

        h, w, _ = img.shape
        # Set input size for YuNet detector
        self.detector.setInputSize((w, h))
        
        # Detect faces
        retval, faces = self.detector.detect(img)
        if retval == 0 or faces is None or len(faces) == 0:
            return None, "No face detected in the image"

        # Select the face with highest confidence (faces is sorted or contains score in col 14)
        # Structure of face info: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc, score]
        face_info = faces[0]
        
        # Crop and align face
        aligned_face = self.recognizer.alignCrop(img, face_info)
        
        # Extract features (128-dimensional float embedding)
        embedding = self.recognizer.feature(aligned_face)
        return embedding[0].tolist(), None

    def compare_embeddings(self, emb1, emb2):
        """
        Compares two embeddings (lists of floats) and returns the similarity score.
        SFace matches using Cosine Similarity or L2 distance.
        We return Cosine Similarity which is typically between -1.0 and 1.0 (threshold is usually around 0.36 for SFace).
        """
        e1 = np.array(emb1, dtype=np.float32).reshape(1, -1)
        e2 = np.array(emb2, dtype=np.float32).reshape(1, -1)
        
        # Compute cosine similarity
        score = self.recognizer.match(e1, e2, cv2.FR_COSINE)
        return float(score)
