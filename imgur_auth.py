import configparser
import webbrowser
from imgur_python import Imgur

config = configparser.ConfigParser()
config.read(r'keys.ini')
imgur_client = Imgur({'client_id': config['keys']['imgur_client_id'],
                      'client_secret': config['keys']['imgur_client_secret'],
                      'access_token': config['keys']['imgur_access_token'],
                      'refresh_token': config['keys']['imgur_refresh_token']})
auth_url = imgur_client.authorize()
webbrowser.open(auth_url)
