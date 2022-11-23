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
- pyshorteners
- FuzzyWuzzy
- rich
- maybe more?...

You'll need keys:
- Twitch login key
- Twitch Dev client id and secret
- openai api key
- Oxford Dictionary api key
- open weather maps api key
- google cloud platform api key with timezone and geocoding apis enabled
- detect language api key
- To use pubsub you'll need an oauth key with the proper scope: 'channel:read:redemptions'
- To use settitle and setgame you'll need an outath key with the proper scope: 'channel:manage:broadcast'
- Note: both of the custom scope keys are the same key, just make sure you request both scopes.

Get the pokedex at https://github.com/fanzeyi/pokemon.json/blob/master/pokedex.json
