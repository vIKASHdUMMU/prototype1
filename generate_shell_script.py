import requests
from requests.auth import HTTPBasicAuth
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# --- Jira Config ---
JIRA_BASE_URL = "https://vikashdummu96.atlassian.net"
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")    # Get API Token: https://id.atlassian.com/manage-profile/security/api-tokens


# --- OpenAI Config ---
client = OpenAI()  # Assumes OPENAI_API_KEY is set in env or .env

# --- Get Issue from Jira ---
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
        # Attempt to extract plain text in case of ADF (Atlassian Document Format)
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

# --- Generate the shell script from summary and description using OpenAI ---
def generate_shell_script_from_story(summary, description):
    system_prompt = """
You are an expert DevOps engineer. When given the title and description of a Jira user story, provide a step-by-step technical reasoning for turning this requirement into a Unix shell script, then output the final script. Format your response as follows:

### Reasoning
[Detailed reasoning and mapping of requirements.]

### Unix Shell Script
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

# --- Main execution ---
if __name__ == "__main__":
    # 1. Fetch summary and description from Jira
    summary, description = fetch_jira_issue('SCRUM-2')

    # 2. Generate shell script
    reasoning_and_script = generate_shell_script_from_story(summary, description)

    # 3. Output
    print(reasoning_and_script)