
import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from openai import OpenAI

load_dotenv()
app = Flask(__name__)

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# validate required environment variables
if not JIRA_BASE_URL:
    raise RuntimeError("JIRA_BASE_URL environment variable is not set")
if not JIRA_EMAIL:
    raise RuntimeError("JIRA_EMAIL environment variable is not set")
if not JIRA_API_TOKEN:
    raise RuntimeError("JIRA_API_TOKEN environment variable is not set")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=OPENAI_API_KEY)

def fetch_jira_issue(issue_key):
    endpoint = f"/rest/api/3/issue/{issue_key}"
    params = {"fields": "summary,description"}
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json"}
    response = requests.get(
        JIRA_BASE_URL + endpoint, headers=headers, auth=auth, params=params
    )
    if response.status_code == 200:
        issue = response.json()
        summary = issue["fields"].get("summary", "")
        description = issue["fields"].get("description", "")
        if isinstance(description, dict) and "content" in description:
            def adf_to_text(adf_content):
                result = []
                if isinstance(adf_content, dict):
                    adf_content = [adf_content]
                for node in adf_content:
                    if node.get("type") == "text":
                        result.append(node.get("text", ""))
                    if "content" in node:
                        result.append(adf_to_text(node["content"]))
                return " ".join(result)
            plain_description = adf_to_text(description.get("content", []))
        else:
            plain_description = description if isinstance(description, str) else ""
        return summary, plain_description
    else:
        raise Exception(f"Jira API Error: {response.status_code} - {response.text}")

def generate_shell_script_from_story(summary, description):
    system_prompt = """
    You are an expert DevOps engineer. When given the title and description of a Jira user story, provide a step-by-step technical reasoning for turning this requirement into a Unix shell script, then output the final script. Format your response as follows:

    Reasoning
    [Detailed reasoning and mapping of requirements.]

    Unix Shell Script
    [Executable bash script; no code fencing, just plaintext.]
    """
    user_prompt = f"""Jira User Story Title: {summary}

    Jira User Story Description: {description}

    Please analyze this user story, reason through implementation, and produce a complete Unix shell script in the requested format.
    """
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1200,
        temperature=0.15
    )
    return response.choices[0].message.content

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate_script', methods=['POST'])
def generate_script():
    data = request.json
    issue_key = data.get("issue_key", "").strip()
    if not issue_key:
        return jsonify({"error": "No issue key provided"}), 400
    try:
        summary, description = fetch_jira_issue(issue_key)
        result = generate_shell_script_from_story(summary, description)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
