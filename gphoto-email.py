"""
MIT License

Copyright (c) 2021 scudre

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

=============================================================================

Google Photos --> Email Bridge

Script to check a Google Photos Album for new pictures.  If pictures are found,
they're emailed to the specificed email address.  Add this script to your
cronttab to have it check for new pictures on a regular frequency

This was created for the Skylight Frame (https://www.skylightframe.com). The 
electroic frame loads pictures that are sent as attachments to
an email address.
"""
import pickle
import base64
import imghdr
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from os.path import exists

from googleapiclient.discovery import build

# Set email address, and album id 
TO_ADDRESS = ''
ALBUM_ID = ''

logger = logging.getLogger(__name__)
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly',
          'https://www.googleapis.com/auth/gmail.send']


def get_creds():
    creds = None
    if exists('token.pickle'):
        with open('token.pickle', 'rb') as token_file:
            creds = pickle.load(token_file)

    if not creds or not creds.valid:
        if (creds and creds.expired and creds.refresh_token):
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_console()
        with open('token.pickle', 'wb') as token_file:
            pickle.dump(creds, token_file)

    return creds


def get_image_data(image_url):
    import requests
    rsp = requests.get(image_url, stream=True)
    rsp.raise_for_status()

    return rsp.content


def create_email(images):
    msg = MIMEMultipart()
    msg['Subject'] = 'Pictures'
    msg['From'] = 'me'
    msg['To'] = TO_ADDRESS

    for _, filename, image_url in images:
        image_data = get_image_data(image_url)
        attach_msg = MIMEImage(image_data, _subtype=imghdr.what(None, image_data))
        attach_msg.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attach_msg)

    b64_bytes = base64.urlsafe_b64encode(msg.as_bytes())

    return {'raw': b64_bytes.decode()}


def send_email(creds, message):
    service = build('gmail', 'v1', credentials=creds)
    service.users().messages().send(userId='me', body=message).execute()


def bulk_email_send(creds, images):
    idx = 0
    while images[idx:idx+4]:
        logger.info('Downloading images...')
        messages = create_email(images[idx:idx+4])
        rsp = send_email(creds, messages)
        logger.info('Email sent')
        idx += 4


def load_uploaded_image_list():
    uploaded_images = set()
    if exists('uploaded_images.pickle'):
        with open('uploaded_images.pickle', 'rb') as uploaded_images_file:
            uploaded_images = pickle.load(uploaded_images_file)

    return uploaded_images


def get_new_images(creds):
    service = build('photoslibrary', 'v1', credentials=creds)
    response = service.mediaItems().search(body={'albumId': ALBUM_ID}).execute()
    items = response.get('mediaItems', [])
    
    uploaded_images = load_uploaded_image_list()
    images = [(item.get('id'), item.get('filename'), '{}=d'.format(item.get('baseUrl')))
              for item in items if item.get('id') not in uploaded_images]

    return images


def update_uploaded_image_list(images):
    uploaded_images = load_uploaded_image_list()
    uploaded_images.update([id for id, _, _ in images])
    with open('uploaded_images.pickle', 'wb') as uploaded_images_file:
        pickle.dump(uploaded_images, uploaded_images_file)


def init_logging():
    logger.setLevel(logging.INFO)
    console_hdlr = logging.StreamHandler()
    formatter = logging.Formatter(fmt='[%(levelname)s] %(message)s')
    console_hdlr.setFormatter(formatter)
    logger.addHandler(console_hdlr)
    
    
def main():
    init_logging()
    if not TO_ADDRESS or not ALBUM_ID:
        logger.error('Please set TO_ADDRESS and ALBUM_ID.  Exiting.')
        return
    
    creds = get_creds()
    logger.info('Checking for new images')
    images = get_new_images(creds)
    if images:
        logger.info('%d new images found', len(images))
        bulk_email_send(creds, images)
        update_uploaded_image_list(images)
    else:
        logger.info('No new images found')


if __name__ == '__main__':
    main()
