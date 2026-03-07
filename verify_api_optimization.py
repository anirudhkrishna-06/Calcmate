import subprocess
import time
import requests
import sys
import os

def test_api():
    # 1. Start API Server
    print("🚀 Starting API server...")
    # api_server.py is in the root directory (e:\Projects\Calcmate\MathMend-Project-)
    # We are writing this to verify_api.py in the same root for simplicity
    process = subprocess.Popen(
        [sys.executable, "api_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # 2. Wait for health check
        base_url = "http://localhost:8000"
        max_retries = 120  # Increased to 240 seconds
        for i in range(max_retries):
            try:
                resp = requests.get(f"{base_url}/health")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"🔎 Health Check: {data}")
                    if data.get("pipeline_loaded"):
                        print("✅ API is healthy and pipeline loaded.")
                        break
            except requests.exceptions.ConnectionError:
                pass
            
            print(f"⏳ Waiting for API... ({i+1}/{max_retries})")
            time.sleep(2)
        else:
            print("❌ API failed to start within timeout.")
            # Kill process first to ensure we can read outputs
            process.terminate()
            stdout, stderr = process.communicate()
            print("--- API STDOUT ---")
            print(stdout)
            print("--- API STDERR ---")
            print(stderr)
            return

        # 3. Test Chat Endpoint
        print("\n🧪 Testing /chat endpoint...")
        start_time = time.time()
        chat_payload = {"question": "What is 10 + 20?"}
        chat_resp = requests.post(f"{base_url}/chat", json=chat_payload)
        request_latency = (time.time() - start_time) * 1000
        
        if chat_resp.status_code == 200:
            data = chat_resp.json()
            print(f"✅ Chat response received in {request_latency:.2f}ms")
            print(f"   Answer: {data.get('answer')}")
            print(f"   Latency (server-reported): {data.get('latency_ms', 'N/A')}ms")
        else:
            print(f"❌ Chat request failed: {chat_resp.text}")

        # 4. Test OCR Endpoint
        print("\n🧪 Testing /ocr endpoint...")
        # create a dummy image if not exists
        dummy_img_path = "test_ocr_image.png"
        if not os.path.exists(dummy_img_path):
             from PIL import Image
             img = Image.new('RGB', (100, 30), color = (255, 255, 255))
             from PIL import ImageDraw
             d = ImageDraw.Draw(img)
             d.text((10,10), "Hello", fill=(0,0,0))
             img.save(dummy_img_path)

        with open(dummy_img_path, "rb") as f:
            start_time = time.time()
            ocr_resp = requests.post(f"{base_url}/ocr", files={"image": f})
            request_latency = (time.time() - start_time) * 1000
        
        if ocr_resp.status_code == 200:
            data = ocr_resp.json()
            print(f"✅ OCR response received in {request_latency:.2f}ms")
            print(f"   Extracted: {data.get('extracted_text')}")
            print(f"   Latency (server-reported): {data.get('latency_ms', 'N/A')}ms")
        else:
            print(f"❌ OCR request failed: {ocr_resp.text}")
            
        # 5. Test OCR Caching (Second Hit)
        print("\n🧪 Testing /ocr endpoint (2nd hit for cache check)...")
        with open(dummy_img_path, "rb") as f:
            start_time = time.time()
            ocr_resp = requests.post(f"{base_url}/ocr", files={"image": f})
            request_latency = (time.time() - start_time) * 1000
            
        if ocr_resp.status_code == 200:
            data = ocr_resp.json()
            print(f"✅ OCR (2nd hit) response received in {request_latency:.2f}ms")
            print(f"   Latency (server-reported): {data.get('latency_ms', 'N/A')}ms")
        else:
            print(f"❌ OCR (2nd hit) request failed: {ocr_resp.text}")
            
        # Cleanup
        if os.path.exists(dummy_img_path):
            os.remove(dummy_img_path)

    except Exception as e:
        print(f"❌ Verification failed with exception: {e}")
    finally:
        print("\n🛑 Stopping API server...")
        try:
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            # print("STDOUT:", stdout) # Optional: uncomment if needed
            # print("STDERR:", stderr)
        except:
            process.kill()

if __name__ == "__main__":
    test_api()
