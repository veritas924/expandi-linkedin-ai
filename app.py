from flask import Flask, request, jsonify
import requests
import openai
import os
from serpapi import GoogleSearch
from dotenv import load_dotenv

# Load environment variables (for local testing; Render injects env vars automatically)
load_dotenv()

# API keys from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
EXPANDI_WEBHOOK_URL = os.getenv("EXPANDI_WEBHOOK_URL")

# Initialize Flask app
app = Flask(__name__)

@app.route('/incoming-expandi-lead', methods=['POST'])
def receive_lead():
    try:
        data = request.json
        first_name = data.get('first_name')  # from Expandi payload
	    last_name = data.get('company_name') or "Professional"  # fallback if missing
	    linkedin_url = data.get('profile_link')  # from Expandi payload

        if not (first_name and linkedin_url):
    	return jsonify({"status": "Webhook received, but missing essential fields"}), 200

        # Step 1: Enrich LinkedIn public info
        title, about_section = scrape_linkedin_profile(first_name, last_name)

        # Step 2: Generate personalized message with OpenAI
        personalized_message = generate_personalized_message(first_name, last_name, title, about_section)

        # Step 3: Send enriched lead + message back to Expandi
        send_to_expandi(first_name, last_name, linkedin_url, personalized_message)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

def scrape_linkedin_profile(first_name, last_name):
    search = GoogleSearch({
        "engine": "google",
        "q": f"{first_name} {last_name} LinkedIn",
        "api_key": SERPAPI_API_KEY,
        "num": 1
    })
    results = search.get_dict()

    if "organic_results" not in results or len(results["organic_results"]) == 0:
        return "Professional", "Experienced professional in their field."

    first_result = results["organic_results"][0]
    title = first_result.get("title", "Professional")
    snippet = first_result.get("snippet", "Experienced professional in their field.")
    return title, snippet

def generate_personalized_message(first_name, last_name, title, about_section):
    openai.api_key = OPENAI_API_KEY

    prompt = (
        f"Write a short, friendly LinkedIn connection message to {first_name} {last_name}. "
        f"Their LinkedIn headline is: \"{title}\". "
        f"Their About section says: \"{about_section}\". "
        f"Keep the message 1–2 sentences. "
        f"At the end, mention that Golden West specializes in providing high-performance human biological matrices "
        f"for assay development and biomarker controls. "
        f"Make it sound casual, professional, and conversational, not robotic."
    )

    response = openai.ChatCompletion.create(
        model="gpt-4o",   # ✅ using GPT-4o for better cost and speed
        messages=[
            {"role": "system", "content": "You are a helpful assistant writing LinkedIn connection messages."},
            {"role": "user", "content": prompt}
        ]
    )

    return response['choices'][0]['message']['content'].strip()

def send_to_expandi(first_name, last_name, linkedin_url, personalized_message):
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "linkedinUrl": linkedin_url,
        "customMessage": personalized_message
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(EXPANDI_WEBHOOK_URL, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"Failed to send to Expandi: {response.text}")

# Run the app (Render uses gunicorn to start it automatically, so no debug needed)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
