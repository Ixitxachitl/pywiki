# pywiki
A twitch chatbot that can answer all your questions.
Run on windows if you want to use reddit, it uses a ctypes popup.

Requirements:
- twitchio
- wikipedia
- dateutil
- openai
- pyowm
- deep_translator
- geopy
- pytz
- pyttsx3
- pycountry
- py2snes
- dateutil
- Cinemagoer
- BeautifulSoup
- FuzzyWuzzy
- rich
- stability_sdk
- imgur_python
- maybe more?...

You'll need keys:
- Twitch login key
- Twitch Dev client id and secret
- openai api key
- Oxford Dictionary api key
- open weather maps api key
- google cloud platform api key with timezone and geocoding apis enabled
- detect language api key
- NASA api key for APOD
- To use pubsub you'll need an oauth key with the proper scope: 'channel:read:redemptions'
- To use settitle and setgame you'll need an oauth key with the proper scope: 'channel:manage:broadcast'
- Note: both of the custom scope keys are the same key, just make sure you request both scopes.
- to authorize imgur obtain a client id and use the imgur_auth.py script to login and parse the return url, https://imgur-python.readthedocs.io/en/latest/authorize/
- imgur currently has a bug in the reauthorizing script that breaks things, to fix temporarily replace Authorize.py with the on in this project 

Get the pokedex at https://github.com/fanzeyi/pokemon.json/blob/master/pokedex.json
