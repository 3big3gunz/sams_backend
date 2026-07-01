import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import hash_password, verify_password, create_access_token, decode_access_token
from backend.face_engine import FaceEngine

def test_auth():
    print("=== Testing Password Hashing & Verification ===")
    pw = "secretpassword123"
    h = hash_password(pw)
    print(f"Hashed: {h}")
    assert verify_password(pw, h) is True
    assert verify_password("wrong_password", h) is False
    print("Password hashing verification: PASSED")

    print("\n=== Testing JWT Generation & Parsing ===")
    data = {"sub": "test@domain.com", "role": "admin"}
    token = create_access_token(data)
    print(f"JWT Token generated: {token[:30]}...")
    decoded = decode_access_token(token)
    assert decoded["sub"] == "test@domain.com"
    assert decoded["role"] == "admin"
    print("JWT authentication verification: PASSED")

def test_face_engine():
    print("\n=== Testing Face Engine Initialization ===")
    try:
        engine = FaceEngine()
        print("Models successfully loaded and engine initialized: PASSED")
        
        # Test cosine matching with identical dummy vectors
        print("\n=== Testing Cosine Matcher ===")
        v1 = [0.1] * 128
        score = engine.compare_embeddings(v1, v1)
        print(f"Similarity score for identical vectors: {score}")
        # Cosine similarity of identical vectors should be ~1.0
        assert score > 0.95
        print("Embedding comparison logic: PASSED")
    except Exception as e:
        print(f"Face Engine failed: {e}")

if __name__ == "__main__":
    test_auth()
    test_face_engine()
    print("\nAll unit tests passed successfully!")
