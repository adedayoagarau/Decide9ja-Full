import sys
import os
 
# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_twilio_webhook():
    print("Testing Twilio Webhook...")
    try:
        response = client.post(
            "/webhook",
            data={
                "From": "whatsapp:+2348000000000",
                "Body": "Hello Decide9ja",
                "ProfileName": "Tester"
            }
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200 and "<Response>" in response.text:
            print("✅ integration SUCCESS")
        else:
            print("❌ integration FAILED")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_twilio_webhook()
