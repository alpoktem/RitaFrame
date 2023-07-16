import pickle
import os
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
#from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import requests
import json
# import pandas as pd


class GooglePhotosApi:
    def __init__(self,
                 api_name = 'photoslibrary',
                 client_secret_file= r'./credentials/client_secret.json',
                 api_version = 'v1',
                 scopes = ['https://www.googleapis.com/auth/photoslibrary']):
        '''
        Args:
            client_secret_file: string, location where the requested credentials are saved
            api_version: string, the version of the service
            api_name: string, name of the api e.g."docs","photoslibrary",...
            api_version: version of the api

        Return:
            service:
        '''

        self.api_name = api_name
        self.client_secret_file = client_secret_file
        self.api_version = api_version
        self.scopes = scopes
        self.cred_pickle_file = f'./credentials/token_{self.api_name}_{self.api_version}.pickle'

        self.cred = None

    def run_local_server(self):
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

def get_photos_in_album(album_id, creds):
    url = 'https://photoslibrary.googleapis.com/v1/mediaItems:search'
    payload = {
                  "albumId": album_id
              }
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer {}'.format(creds.token)
    }
    
    try:
        res = requests.request("POST", url, data=json.dumps(payload), headers=headers)
    except:
        print('Request error') 
    
    return(res)



def get_album_id_from_album_name(album_name, creds):
    url = 'https://photoslibrary.googleapis.com/v1/albums'

    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer {}'.format(creds.token)
    }
    
    try:
        res = requests.request("GET", url, headers=headers)

        
    except:
        print('Request error') 

    if res.status_code == 200:
        albums_json = res.json()

        for album in albums_json['albums']:
            if album['title'] == album_name:
                return album['id']
    else:
        print(res.status_code, res.text)

    return None

def get_album_df(album_name, creds):

    df = pd.DataFrame()

    album_id = get_album_id_from_album_name(album_name, creds)

    if not album_id:
        print(f"ERROR: Album with name {album_id} not found")
    else:
        # create request for specified album
        response = get_photos_in_album(album_id, creds)

        data = response.json()
        
        media_items = data.get("mediaItems", [])
        df = pd.DataFrame(media_items)

        # Extract desired columns (TODO: Sometimes data is empty and this line fails)
        df = df[["baseUrl", "mediaMetadata", "filename", "mimeType"]]

        # Extract additional columns from mediaMetadata
        df["creationTime"] = df["mediaMetadata"].apply(lambda x: x.get("creationTime"))
        df["width"] = df["mediaMetadata"].apply(lambda x: x.get("width"))
        df["height"] = df["mediaMetadata"].apply(lambda x: x.get("height"))

        # Clean up the DataFrame
        df.drop("mediaMetadata", axis=1, inplace=True)

        df = df.sort_values(by="creationTime", ascending=False)

        #DEBUG print
        columns_to_print = ["filename", "creationTime", "mimeType", "width", "height"]
        print(df.loc[:, columns_to_print].to_string(index=True))

    return df

def get_album_dict(album_name, creds):
    album_dict = {}
    album_id = get_album_id_from_album_name(album_name, creds)

    if not album_id:
        print(f"ERROR: Album with name {album_id} not found")
    else:
        # create request for specified album
        response = get_photos_in_album(album_id, creds)

        data = response.json()

        media_items = data.get("mediaItems", [])
        album_dict = {
            "baseUrl": [],
            "filename": [],
            "mimeType": [],
            "creationTime": [],
            "width": [],
            "height": []
        }

        for item in media_items:
            album_dict["baseUrl"].append(item.get("baseUrl"))
            album_dict["filename"].append(item.get("filename"))
            album_dict["mimeType"].append(item.get("mimeType"))
            album_dict["creationTime"].append(item.get("mediaMetadata", {}).get("creationTime"))
            album_dict["width"].append(item.get("mediaMetadata", {}).get("width"))
            album_dict["height"].append(item.get("mediaMetadata", {}).get("height"))

        # Sort the album dictionary by creationTime
        album_dict = {k: v for k, v in sorted(album_dict.items(), key=lambda x: x[1])}

        #DEBUG print
        print("filename", "creationTime", "mimeType", "width", "height")
        for i in range(len(album_dict["filename"])):
            print(album_dict["filename"][i], album_dict["creationTime"][i], album_dict["mimeType"][i],
                  album_dict["width"][i], album_dict["height"][i])

    return album_dict

