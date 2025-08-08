import requests
from trafilatura import extract

def fetch_url_safe(url):
    """
    Safely fetches the content of a given URL while handling various HTTP responses and exceptions.

    Args:
        url (str): The URL to fetch.

    Returns:
        dict: A dictionary containing the following keys:
            - success (bool): Indicates whether the fetch was successful.
            - content (str): The extracted content from the URL if successful, otherwise an empty string.
            - error (str): An error message if the fetch was unsuccessful, otherwise an empty string.

    Behavior:
        - Handles HTTP status codes:
            - 200, 202: Successfully fetches and processes the content.
            - 301, 302: Indicates a redirection and returns an error message.
            - 403: Indicates a forbidden access and returns an error message.
            - 404: Indicates the resource was not found and returns an error message.
            - Other status codes: Returns a generic error message.
        - Catches and handles exceptions:
            - `requests.exceptions.RequestException`: Handles request-related errors.
            - General exceptions: Catches any other unexpected errors.
        - Prints debug information for each case, including HTTP status codes and errors.

    Note:
        - The function uses a timeout of 3 seconds for the HTTP request.
        - Redirects are disabled (`allow_redirects=False`).
    """
    try:
        response = requests.get(url, allow_redirects = False, timeout = 3)
        print(response)
        if response.status_code == 403:
            print("403 Forbidden error encountered.")
            return {"success": False, "content": "", "error": "403 Forbidden"}
        elif response.status_code in [301, 302]:
            print("Redirected to:", response.headers.get("Location"))
            return {"success": False, "content": "", "error": "Redirected from provided page"}
        elif response.status_code in [200, 202]:
            print("No redirect. Extracting...")
            result = extract(response.text, url=url, fast=True)
            return {"success": True, "content": result, "error": ""}
        elif response.status_code == 404:
            print("404 Not Found error encountered.")
            return {"success": False, "content": "", "error": "404 Not Found"}
        else:
            print("Error encountered.")
            return {"success": False, "content": "", "error": "Error fetching content"}
    except requests.exceptions.RequestException as e:
        print("Error:", str(e))
        return {"success": False, "content": "", "error": str(e)}
    except Exception as e:
        print("Error:", str(e))
        return {"success": False, "content": "", "error": str(e)}