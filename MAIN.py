import os
from flask import Flask, jsonify, redirect, render_template, request, url_for
import requests
from bs4 import BeautifulSoup
import openai
from OPENAI_API_KEY import api_data
import time

app = Flask(__name__, template_folder='templates')

# Ensure you have your OpenAI API key set in your environment variables or configure it directly
openai.api_key = api_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/info')
def infoPage():
    return render_template('info.html')

def generate_google_dork_urls(base_query):
    base_url = "https://www.google.com/search?q="
    dork_patterns = [
        f'"{base_query}"',
        f'{base_query} site:facebook.com OR site:instagram.com OR site:twitter.com OR site:myspace.com OR site:snapchat.com OR site:x.com OR site:tiktok.com OR site:pinterest.com',
        f'{base_query} filetype:pdf OR filetype:doc OR filetype:docx',
        f'{base_query} "contact" OR "about" site:.org OR site:.com',
        f'{base_query} email OR contact OR @ OR address OR phone number',
    ]
    return [base_url + requests.utils.quote(dork_query) for dork_query in dork_patterns]

def save_webpage_text(url, output_file_path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        with open(output_file_path, 'a', encoding='utf-8') as file:
            file.write(f"\n\nURL: {url}\n{text}")
        print(f"Webpage text for {url} has been saved.")
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")

def setup_openai():
    # Initialize the OpenAI client
    client = openai.OpenAI()

    # Create a file in OpenAI
    file = client.files.create(
        file=open('dump_text.txt', "rb"),
        purpose='assistants'
    )

    # Create an Assistant
    assistant = client.beta.assistants.create(
        name="EnumSpider",
        instructions="Before responding, always use Chain-of-thought and Chain-or-reasoning to assist the user to the best of your ability. Read the provided .txt file by using code interpreter to break it into digestable piece for you to read. Once you have completed reading the text, respond to the users' query with pertinant information. Always provide direct links to social media handles and other forms of media like linkedin. Never explain to the user that the information comes from the dump_text.txt. Merely, provide them with the detailed information they are requesting. You have the code_interpreter and retrieval tool at your disposal. Please utilize them for effiency. ALL URL links must be provided for the user to copy and paste.",
        model="gpt-4-1106-preview",
        tools=[{"type": "code_interpreter"}, {"type": "retrieval"}],
        file_ids=[file.id]
    )

    # Create a Thread
    thread = client.beta.threads.create()

    return client, assistant.id, thread.id

def query_openai(client, assistant_id, thread_id, query):
    # Omitting the previous steps for brevity; assuming they're unchanged
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions="Task: Provide the user with useful data for OSINT analysis. Include information such as work information, possible identity, phone numbers, social media handles, employment, and anything else you believe is relevant."+ query
    )
    # This function now returns the messages, so capture it
    return check_run_status(client, thread_id, run.id)  # Ensure this also returns the display_messages output

def check_run_status(client, thread_id, run_id):
    while True:
        time.sleep(5)  # Delay for API rate limiting
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run_status.status == 'completed':
            # Now capturing the return value from display_messages
            return display_messages(client, thread_id)
        else:
            print("Processing...")
    # Consider what to return if not completed successfully
    return "The process did not complete successfully."


def display_messages(client, thread_id):
    response_messages = []
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    for msg in messages.data:
        # You might want to filter by role or ensure it's the type of message you want
        response_messages.append(f"{msg.role.capitalize()}: {msg.content[0].text.value}")
    # Join the messages into a single string or handle them as you see fit
    return " ".join(response_messages)


@app.route('/submit', methods=['POST'])
def submit():
    base_query = " ".join(request.form.get(field) for field in ['name', 'email', 'school', 'employment', 'phone'] if request.form.get(field))
    print(f"Base Query: {base_query}")
    google_dork_urls = generate_google_dork_urls(base_query)
    output_path = 'dump_text.txt'
    for url in google_dork_urls:
        print(f"Processing: {url}")
        save_webpage_text(url, output_path)
    return redirect(url_for('infoPage'))

@app.route('/query_openai', methods=['POST'])
@app.route('/query_openai', methods=['POST'])
def query_openai_web():
    data = request.json  # Extract JSON data sent from the front end
    query = data.get('sentence')  # Extract the 'sentence' value from the JSON
    
    client, assistant_id, thread_id = setup_openai()
    # This function now directly returns the message content
    response_text = query_openai(client, assistant_id, thread_id, query)
    
    # Return the response text as part of the JSON response
    return jsonify({"answer": response_text})


if __name__ == "__main__":
    app.run(debug=True)
