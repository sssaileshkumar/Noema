import requests
import random
import time

API_URL = "http://localhost:8001"
NUM_TWEETS = 200

# Random content generators
subjects = ["FastAPI", "Python", "Streamlit", "QA Testing", "SQLAlchemy", "My code", "This app", "Finding bugs"]
actions = ["is blowing my mind.", "needs more coffee.", "is acting weird today.", "works perfectly!", "failed the load test."]
hashtags = ["#devlife", "#qa", "#coding", "#tech", "#bugs"]

def generate_tweet():
    return f"{random.choice(subjects)} {random.choice(actions)} {random.choice(hashtags)} {random.randint(1000, 9999)}"

print("1. Registering bot account...")
credentials = {"username": "qa_spam_bot", "password": "securepassword123"}
requests.post(f"{API_URL}/register", json=credentials)

print("2. Logging in to get token...")
login_res = requests.post(f"{API_URL}/login", json=credentials)

if login_res.status_code != 200:
    print(f"Login failed! {login_res.text}")
    exit()

token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print(f"3. Posting {NUM_TWEETS} tweets...")
success_count = 0

for i in range(NUM_TWEETS):
    tweet_content = generate_tweet()
    res = requests.post(f"{API_URL}/tweets", json={"content": tweet_content}, headers=headers)
    
    if res.status_code == 200:
        success_count += 1
        print(f"[{i+1}/{NUM_TWEETS}] Posted: {tweet_content}")
    else:
        print(f"[{i+1}/{NUM_TWEETS}] Failed: {res.text}")
        
    # Tiny delay to prevent overwhelming the SQLite file lock on standard setups
    time.sleep(0.05)

print(f"\nDone! Successfully posted {success_count} tweets.")