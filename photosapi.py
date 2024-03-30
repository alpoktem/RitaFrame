import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import requests
import json
import time
import logging


class GooglePhotosApi:

    """
    A client for interacting with the Google Photos API.

    Handles authentication, token refresh, and making API calls.
    """

    def __init__(self,
                 api_name = 'photoslibrary',
                 client_secret_file= r'./credentials/client_secret.json',
                 api_version = 'v1',
                 scopes = ['https://www.googleapis.com/auth/photoslibrary']):
        """
        Initializes the API client.

        Args:
            api_name: Name of the API (default: 'photoslibrary').
            client_secret_file: Path to where the client secret JSON file will be saved
            api_version: API version (default: 'v1').
            scopes: List of scopes for which the application requests access.
        """


        self.api_name = api_name
        self.client_secret_file = client_secret_file
        self.api_version = api_version
        self.scopes = scopes
        self.cred_pickle_file = f'./credentials/token_{self.api_name}_{self.api_version}.pickle'
        self.authenticate()

    def authenticate(self):
        """
        Authenticates the user and obtains access credentials.

        Tries to load credentials from a pickle file. If not found or invalid,
        initiates the authentication flow to obtain new credentials.

        Returns:
            The authenticated credentials.
        """

        # is checking if there is already a pickle file with relevant credentials
        if os.path.exists(self.cred_pickle_file):
            with open(self.cred_pickle_file, 'rb') as token:
                self.cred = pickle.load(token)

        # if there is no pickle file with stored credentials, create one using google_auth_oauthlib.flow
        if not self.cred or not self.cred.valid:
            if self.cred and self.cred.expired and self.cred.refresh_token:
                self.cred.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, self.scopes)
                self.cred = flow.run_local_server()

            with open(self.cred_pickle_file, 'wb') as token:
                pickle.dump(self.cred, token)
        
        return self.cred

    def make_api_call(self, method, url, payload=None, headers=None, retries=3, retry_delay=1):
        """Makes an API call with automatic token refresh if necessary and retries on failures.

        Args:
            method (str): The HTTP method to use ('GET', 'POST', etc.).
            url (str): The URL for the API request.
            payload (dict, optional): The payload to send in the request body (for POST requests).
            headers (dict, optional): Additional headers to include in the request.
            retries (int): Number of times to retry the request on server errors.
            retry_delay (int): Delay in seconds before retrying the request.

        Returns:
            The response from the API call or None in case of failure.
        """
        # Ensure headers include the refreshed token
        if headers is None:
            headers = {}
        headers['Authorization'] = 'Bearer {}'.format(self.cred.token)
        
        for attempt in range(retries + 1):
            try:
                response = requests.request(method, url, headers=headers, json=payload)
                response.raise_for_status()  # Raises an HTTPError for 4XX or 5XX responses
                
                return response  # Success, return the response object

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                
                if status_code == 401 and self.cred.expired and self.cred.refresh_token:
                    # Attempt to refresh the access token
                    logging.info("Access token expired. Attempting to refresh.")
                    self.cred.refresh(Request())
                    with open(self.cred_pickle_file, 'wb') as token:
                        pickle.dump(self.cred, token)
                    headers['Authorization'] = 'Bearer {}'.format(self.cred.token)  # Update the token in headers
                    continue  # Retry the request with the refreshed token

                elif 500 <= status_code <= 599:
                    # Server error, attempt retry
                    logging.warning(f"Server error ({status_code}): {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue  # Retry the request
                
                else:
                    # For other HTTP errors, do not retry
                    logging.error(f"HTTP Error: {e}")
                    break

            except Exception as e:
                logging.error(f"Error making API call: {e}")
                break  # Break on non-retryable errors
        
        return None  # If retries are exhausted or a non-retryable error occurs, return None


    def get_album_id_from_album_name(self, album_name):
        """
        Finds an album's ID by its name in Google Photos.

        Args:
            album_name (str): Name of the album.

        Returns:
            str or None: The album ID if found, otherwise None.
        """

        url = 'https://photoslibrary.googleapis.com/v1/albums'
        response = self.make_api_call("GET", url)
        if response and response.status_code == 200:
            albums_json = response.json()
            for album in albums_json['albums']:
                if album['title'] == album_name:
                    return album['id']
        return None

    def get_photos_in_album(self, album_id):
        """
        Retrieves photos from a specified Google Photos album.

        Args:
            album_id (str): ID of the album to fetch photos from.

        Returns:
            requests.Response or None: The API response, or None on failure.
        """

        url = 'https://photoslibrary.googleapis.com/v1/mediaItems:search'
        payload = {"albumId": album_id}

        # Use the new make_api_call method to handle token validation and refreshing
        response = self.make_api_call("POST", url, payload=payload)

        # Handle the response based on whether the request was successful
        if response and response.status_code == 200:
            return response
        else:
            logging.error(f"Failed to retrieve photos from album. Status Code: {response.status_code}" if response else "API call failed.")
            return None



    def get_album_dict(self, album_name):
        """
        Compiles details of photos in a named album into a dictionary.

        Args:
            album_name (str): Name of the album.
            debug_prints (bool): Flag to print out album content (for debugging)

        Returns:
            dict or None: Photo details if album exists, otherwise None.
        """

        album_id = self.get_album_id_from_album_name(album_name)

        if not album_id:
            logging.error(f"ERROR: Album with name {album_name} not found")
            return None

        # Create request for specified album
        response = self.get_photos_in_album(album_id)
        data = response.json()
        media_items = data.get("mediaItems", [])

        album_dict = {
            "items": []
        }

        for item in media_items:
            media_metadata = item.get("mediaMetadata", {})
            item_info = {
                "baseUrl": item.get("baseUrl"),
                "filename": item.get("filename"),
                "mimeType": item.get("mimeType"),
                "creationTime": media_metadata.get("creationTime"),
                "width": media_metadata.get("width"),
                "height": media_metadata.get("height")
            }
            album_dict["items"].append(item_info)

        # Sort items by creationTime in descending order
        album_dict["items"].sort(key=lambda x: x["creationTime"], reverse=True)

        # List photos for debug
        logging.debug("{:<20} {:<25} {:<15} {:<10} {:<10}".format("Filename", "Creation Time", "MIME Type", "Width", "Height"))
        for item in album_dict["items"]:
            logging.debug("{:<20} {:<25} {:<15} {:<10} {:<10}".format(item["filename"], item["creationTime"],
                                                             item["mimeType"], item["width"], item["height"]))

        return album_dict



