import json
import base64
import os
import time
import requests
from json import dumps
from flask import Flask, request, jsonify, redirect, session, Response
from dotenv import load_dotenv
from urllib.parse import urlencode
from flask import Flask, jsonify
from flask_cors import CORS

from html_extraction import scrape, process_results
from customTypes import ConvertResult

# Load .env variables
load_dotenv()
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

MAIN_REPO = "ShishirPatil/gorilla"

DEPLOYMENT = True
if DEPLOYMENT:
    FRONTEND_URL = "http://localhost:3000/addapi/"
    PORT = 80
    HOST = "34.133.163.39"
    SERVER_BASEURL = f"http://{HOST}:{PORT}"
    GITHUB_CALLBACK_URL = f"{SERVER_BASEURL}/github/callback"
    ROUTE_PREFIX = "/addapi/"
else:
    FRONTEND_URL = "http://localhost:3000/addapi/"
    PORT = 8080
    HOST = "localhost"
    SERVER_BASEURL = f"http://{HOST}:{PORT}"
    GITHUB_CALLBACK_URL = f"{SERVER_BASEURL}/github/callback"
    ROUTE_PREFIX = "/"


app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app, origins=[FRONTEND_URL], supports_credentials=True)

#########################
### Route Definitions ###
#########################

@app.route(f'{ROUTE_PREFIX}convert', methods=['POST'])
def convert_json():
    """
    Process API URLs and user information to generate structured JSON results.

    This endpoint accepts a POST request containing JSON data with API URLs and a user's name.
    It processes each URL to scrape and extract relevant data, then converts the extracted data into a structured JSON format.

    The JSON payload should include:
    - 'api_urls': a list of URLs to be processed.
    - 'user_name': the username associated with the operation.

    The function performs the following steps:
    - Extracts data from the specified URLs using a web scraping function.
    - Processes the scraped data to generate structured JSON using custom logic.
    - Returns the structured JSON as a response with MIME type 'application/json'.

    Returns:
    - A JSON response containing the processed data on successful execution.
    - An error message and appropriate status code if any errors occur during processing.

    Exceptions:
    - Returns a 400 status code if any required data is missing in the request.
    - Returns a 500 status code if there is an exception during the execution, such as failure in data fetching or processing.
    """
    try:
        option_2_json = request.get_json()
        api_urls = option_2_json.get('api_urls')
        username = option_2_json.get("user_name")
        scrape_results: dict = scrape(api_urls) 

        conversion_results = process_results(scrape_results, option_2_json)
        conversion_json_str = json.dumps(conversion_results, sort_keys=False, indent=2)
        
        return Response(conversion_json_str, status=200, mimetype='application/json')
    except Exception as e:
        print(e)
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')


@app.route(f'{ROUTE_PREFIX}raise-pr', methods=['POST'])
def raise_pr():
    """
    Create a pull request on GitHub for a specified user.

    This endpoint is called with a POST request that includes an 'Authorization' header 
    containing the access token for GitHub and a JSON payload with necessary data. It performs 
    the following operations: forks the repository, creates a new branch, adds a new file 
    containing the results of successful API calls, and prepares the data for a pull request.
    
    The JSON payload must include:
    - 'user_name': The GitHub username of the user for whom the pull request will be raised.
    - 'api_urls': A list of URLs that were called successfully by the client.
    
    The function handles the following:
    - Forking the main repository under the user's GitHub account.
    - Creating a unique branch based on the user's name.
    - Adding a new JSON file with the successful API call results to the new branch.
    - Returning a URL for the GitHub compare page to allow the user to create a pull request 
      via the GitHub UI.

    Returns:
    - A JSON response with the 'compare_url' key pointing to the GitHub compare page, with a 
      200 status code, if the operations are successful.
    - A JSON response with an 'error' message and a 400 status code if the required data is 
      missing from the request.
    - A JSON response with an 'error' message and a 401 status code if the authorization token 
      is missing or incorrect.
    - A JSON response with an 'error' message and a 500 status code if any exceptions occur 
      during the execution of the function.
    """
    access_token = request.headers.get('Authorization')
    if not access_token:
        return jsonify({"error": "Authorization header missing or incorrect"}), 401
    
    # Get JSON data sent from the client
    data = request.get_json()
    if not data or 'user_name' not in data or 'api_urls' not in data:
        return jsonify({"error": "Missing data in request"}), 400
    
    user_name = data['user_name']
    url_results = data['api_urls']
    
    successfulResults = getSuccessfulResults(url_results)
    file_path = f"data/apizoo/{user_name}.json"
    new_branch_name = create_unique_branch_name(user_name)

    try:
        fork_repo_info = fork_repository(MAIN_REPO, access_token)
        fork_repo_name = fork_repo_info['full_name']
        create_branch(fork_repo_name, new_branch_name, access_token)

        commit_message = f"Add new file for {user_name}"
        file_content = dumps(list(successfulResults), indent=2) + '\n'
        create_file_in_repo(fork_repo_name, file_path, commit_message, file_content, new_branch_name, access_token)


        base_branch = "main"
        compare_url = generate_github_compare_url(MAIN_REPO, fork_repo_name, base_branch, new_branch_name)
        # Return the URL for the frontend to handle redirection
        return jsonify({"compare_url": compare_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route(f'{ROUTE_PREFIX}get-access-token', methods=['GET'])
def exchange_code_for_token():
    """
    Exchange an authorization code for an access token from GitHub.

    This endpoint handles the redirection from GitHub OAuth authorization. It takes
    the 'code' parameter from the query string, which is the authorization code
    provided by GitHub after the user has authorized the application. It then
    exchanges this code for an access token using GitHub's access token endpoint.

    Parameters:
    - code (str): The authorization code received from GitHub as a URL query parameter.

    Returns:
    - A redirect to the FRONTEND_URL with the access token included in the query string
      if the exchange is successful.
    - A JSON response with an error message and a 400 status code if the 'code' parameter
      is missing or if the token exchange fails.
    """
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Authorization code is required.'}), 400

    token_url = "https://github.com/login/oauth/access_token"
    headers = {'Accept': 'application/json'}
    payload = {
        'client_id': GITHUB_CLIENT_ID,
        'client_secret': GITHUB_CLIENT_SECRET,
        'code': code,
    }
    # Make the POST request to exchange the code for an access token
    response = requests.post(token_url, headers=headers, data=payload)
    if response.ok:
        token_data = response.json()
        return redirect(f"{FRONTEND_URL}?access_token={token_data['access_token']}")
    else:
        return jsonify({'error': 'Failed to fetch access token'}), response.status_code
    
    
@app.route('/check-access-token', methods=['POST'])
def check_access_token():
    """
    Verify the validity of an access token with GitHub.

    This endpoint expects a JSON payload containing an 'access_token' key. It makes a
    POST request to GitHub's token checking endpoint to verify if the provided access
    token is valid. 

    It is used by the frontend to check if the stored access token is still valid before
    attempting to access GitHub resources.

    JSON Payload:
    - access_token (str): The OAuth access token whose validity needs to be checked.

    Returns:
    - A JSON response with a 'valid' key set to True if the access token is valid.
    - A JSON response with a 'valid' key set to False and the appropriate status code
      if the token is invalid, or if any other errors occur during the validation process.
    """
    data = request.get_json()
    access_token = data.get('access_token')
    if not access_token:
        return jsonify({'error': 'Access token is missing.'}), 400
    
    github_token_check_url = f"https://api.github.com/applications/{GITHUB_CLIENT_ID}/token"
    
    try:
        response = requests.post(
            github_token_check_url,
            auth=(GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET),
            headers={ 'Accept': 'application/vnd.github+json' },
            json={ 'access_token': access_token }
        )
        
        if response.status_code == 200:
            return jsonify({'valid': True})
        else:
            return jsonify({'valid': False, 'status': response.status_code})
    except requests.RequestException as e:
        return jsonify({'error': f'Failed to validate token with GitHub: {str(e)}'}), 500

#################################
## Github API HELPER FUNCTIONS ##
#################################

def generate_github_compare_url(main_repo, forked_repo, target_branch, new_branch_name):
    base_repo_user, repo_name = main_repo.split('/')
    forked_repo_user = forked_repo.split('/')[0]
    return f"https://github.com/{base_repo_user}/{repo_name}/compare/{target_branch}...{forked_repo_user}:{new_branch_name}?expand=1"


def create_unique_branch_name(user_name):
    """Generate a unique branch name to avoid conflicts."""
    timestamp = int(time.time())
    return f"{user_name}-branch-{timestamp}"


def fork_repository(repo, access_token):
    """
    Fork a repository on GitHub using the access token
    """
    url = f"https://api.github.com/repos/{repo}/forks"
    headers = {
        "Authorization": access_token,
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 202:
        return response.json()
    else:
        # Attempt to extract the GitHub error message from the response
        try:
            error_details = response.json()
            error_message = error_details.get('message', 'No error message provided.')
        except ValueError:
            # In case the response body does not contain valid JSON
            error_message = 'No error message provided.'

        # Include the status code and error message in the exception
        raise Exception(f"Failed to fork repository. Status code: {response.status_code}. Error: {error_message}")


def get_latest_commit_sha(access_token, repo, branch="main"):
    """
    Get the latest commit SHA of a branch in a repository using the access token passed in.
    """
    url = f"https://api.github.com/repos/{repo}/git/ref/heads/{branch}"
    headers = {
        "Authorization": access_token,
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["object"]["sha"]
    else:
        raise Exception("Failed to get latest commit SHA.")


def create_branch(repo, branch_name, access_token):
    """
    Create a new branch in a repository using the access token passed in as an arg.
    """
    latest_sha = get_latest_commit_sha(access_token, repo, "main")
    url = f"https://api.github.com/repos/{repo}/git/refs"
    headers = {
        "Authorization": access_token,
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "ref": f"refs/heads/{branch_name}",
        "sha": latest_sha,
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    else:
        raise Exception("Failed to create branch.")


def create_file_in_repo(repo, file_path, commit_message, content, branch, access_token):
    """
    Create or update a file in a specified GitHub repository.

    This function sends a PUT request to the GitHub API to create or update a file at a specified path within a repository on a specific branch. The file content is base64 encoded before being sent.
    """
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": access_token,
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "message": commit_message,
        "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'), 
        "branch": branch,
    }

    response = requests.put(url, headers=headers, json=data)

    if response.status_code in [200, 201]:  # 201 for Created, 200 for Updated
        return response.json()  # Return the JSON response if successful
    else:
        raise Exception(f"Failed to create file: {response.status_code} {response.json()}")


def submit_pull_request(main_repo, title, body, head, base, access_token):
    """Submit a pull request to the main repository."""
    url = f"https://api.github.com/repos/{main_repo}/pulls"
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
    }
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 201:  # 201 Created
        print("Pull request submitted successfully.")
        return response.json()  # Returns the created pull request information
    else:
        raise Exception(f"Failed to create pull request: {response.status_code} {response.json()}")


###########################
## Misc Helper Functions ##
###########################

def getSuccessfulResults(urlResults: ConvertResult): 
    successfulResults = []
    for result in urlResults.values():
        if result["status"] == "success":
            successfulResults.append(result["data"])
        
    return successfulResults



@app.route(f'{ROUTE_PREFIX}hello', methods=["GET"])
def say_hello():
    return jsonify({"msg": "Hello from Flask"})

    
if __name__ == "__main__":
    # TODO: remove debug=True for production.
    # app.run(debug=True, host="localhost", port=PORT)
    app.run(debug = not DEPLOYMENT, host=HOST, port=PORT)
