import queue
import threading
import tkinter.messagebox

import py2snes
import twitchio
from twitchio.ext import pubsub
from twitchio.ext import commands
from twitchio.ext import routines
import asyncio
import wikipedia
import requests
import json
import datetime
from dateutil.relativedelta import relativedelta
import configparser
import random
import re
import openai
from pyowm.owm import OWM
from deep_translator import GoogleTranslator
from deep_translator import single_detection
from geopy import geocoders
from pytz import timezone
import sys
import pyttsx3
import pycountry


class PubSub(object):

    def __init__(self):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        self.my_token = config['keys']['token']
        self.users_oauth_token = config['keys']['pubsub_oauth_token']
        self.users_channel = config['options']['pubsub_channel']
        self.users_channel_id = int(config['options']['pubsub_channel_id'])
        self.client = twitchio.Client(token=self.my_token, initial_channels=[self.users_channel])
        self.client.pubsub = pubsub.PubSubPool(self.client)
        self.topics = [pubsub.channel_points(self.users_oauth_token)[self.users_channel_id]]
        self.snes_connected = 0
        self.snes = py2snes.snes()

        @self.client.event()
        async def event_ready():
            print("Pubsub Ready")
            await self.snes_connect()

        @self.client.event()
        async def event_pubsub_channel_points(event: pubsub.PubSubChannelPointsMessage):
            # print(json.dumps(event._data, indent=4, sort_keys=True))
            channel_name = await self.client.fetch_channels([event.channel_id])
            channel = self.client.get_channel(channel_name[0].user.name)
            event_id = event._data['message']['data']['redemption']['reward']['title']

            ###---EDIT HERE FOR CUSTOM REDEMPTIONS---###
            if event_id == 'Eggs':
                print(self.client.nick + ': 🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚'
                                         '🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚')
                await channel.send('🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚'
                                               '🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚')
            elif event_id == 'TTS':
                user_input = event._data['message']['data']['redemption']['user_input']
                # print(self.client.nick + ': ' + user_input)
                # await channel.send(user_input)
                pyttsx3.speak(user_input)
            elif event_id == "Mushroom":
                await self.snes.PutAddress(([(int('0xF50019', 16), [int('0x01', 16)])]))
            elif event_id == "Cape":
                await self.snes.PutAddress(([(int('0xF50019', 16), [int('0x02', 16)])]))
            elif event_id == "Fire Flower":
                await self.snes.PutAddress(([(int('0xF50019', 16), [int('0x03', 16)])]))

            '''
            elif event_id == 'Echo':
                user_input = event._data['message']['data']['redemption']['user_input']
                print(self.client.nick + ': ' + user_input)
                await channel.send(user_input)
            '''
            ###---END EDIT ZONE---###

    async def snes_connect(self):
        await self.snes.connect()
        devices = await self.snes.DeviceList()
        print(devices)
        try:
            await self.snes.Attach(devices[0])
            print(await self.snes.Info())
            self.snes_connected = 1
        except Exception as e:
            print(str(e) + ' SD2SNES Not Detected')
            self.snes_connected = 0


class Bot(commands.Bot):

    def __init__(self):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        super().__init__(token=config['keys']['token'], prefix='!',
                         initial_channels=config['options']['channel'].split(','))
        self.client_id = config['keys']['client_id']
        self.client_secret = config['keys']['client_secret']
        self.client_credentials = requests.post('https://id.twitch.tv/oauth2/token?client_id='
                                                + self.client_id
                                                + '&client_secret='
                                                + self.client_secret
                                                + '&grant_type=client_credentials'
                                                + '&scope='
                                                + '').json()
        # print(json.dumps(self.client_credentials, indent=4, sort_keys=True))
        self.wiki_cooldown = False
        openai.api_key = config['keys']['openai_api_key']
        # engines = openai.Engine.list()
        # print(engines.data)
        self.ps = PubSub()

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')

        await self.ps.client.pubsub.subscribe_topics(self.ps.topics)
        await self.ps.client.start()

    async def event_message(self, message):
        if message.echo:
            return

        if message.author.name == self.nick:
            return

        if message.content.startswith('! '):
            print('yes')
            message.content = message.content[0:1] + message.content[2:].strip()

        print(message.author.name + ': ' + message.content)

        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        chatters = json.loads(config.get('variables', 'chatters'))
        if message.author.name not in chatters:
            chatters.append(message.author.name)
            config['variables']['chatters'] = json.dumps(chatters)
            with open('keys.ini', 'w') as configfile:
                config.write(configfile)
            if config['options']['welcome_enabled'] == 'True':

                ###---EDIT HERE FOR CUSTOM WELCOMES---###
                '''
                if message.author.name == '':
                    response = ''
                    print(self.nick + ': ' + response)
                    await message.channel.send(response)
                '''

                if message.author.is_subscriber or message.author.is_mod or message.author.is_vip:
                    response = self.ai_complete(message.content)
                    try:
                        print(self.nick + ': ' + response.choices[0].text.strip())
                        await message.channel.send(
                            response.choices[0].text.strip().replace('\r', ' ').replace('\n', ' ')[:500])
                    except AttributeError as e:
                        print(self.nick + ': ' + response)
                        await message.channel.send(response)
                ###---END EDIT ZONE---###

        await self.handle_commands(message)

    @routines.routine(iterations=1)
    async def wiki_cooldown_routine(self):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        countdown = int(config['options']['wiki_cooldown'])
        while countdown != 0:
            await asyncio.sleep(1)
            print(countdown, end=" ")
            countdown -= 1
        self.wiki_cooldown = False

    @commands.command()
    async def wiki(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['wiki_enabled'] == 'True':
            if not self.wiki_cooldown:
                wikipedia.set_lang("en")

                try:
                    try:
                        p = wikipedia.summary(ctx.message.content.split(' ', 1)[1], sentences=3, auto_suggest=False)
                    except wikipedia.DisambiguationError as e:
                        print('\n'.join('{}: {}'.format(*k) for k in enumerate(e.options)))
                        p = wikipedia.summary(str(e.options[0]), sentences=3, auto_suggest=False)
                except:
                    try:
                        p = wikipedia.summary(ctx.message.content.split(' ', 1)[1], sentences=3, auto_suggest=True)
                    except wikipedia.DisambiguationError as e:
                        print('\n'.join('{}: {}'.format(*k) for k in enumerate(e.options)))
                        p = wikipedia.summary(str(e.options[0]), sentences=3, auto_suggest=False)
                    except wikipedia.PageError as e:
                        p = str(e)
                print(self.nick + ": " + p)
                await ctx.send(p.replace('\r', '').replace('\n', '')[:500])
                self.wiki_cooldown = True
                self.wiki_cooldown_routine.start()

    @commands.command()
    async def followage(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['followage_enabled'] == 'True':
            headers = {'Client-ID': self.client_id,
                       'Authorization': 'Bearer ' + self.client_credentials['access_token']}
            url_to = 'https://api.twitch.tv/helix/users?login=' + ctx.channel.name
            to_id = requests.get(url_to, headers=headers).json()['data'][0]['id']
            url_from = 'https://api.twitch.tv/helix/users?login=' + ctx.author.name
            from_id = requests.get(url_from, headers=headers).json()['data'][0]['id']
            url_follow = 'https://api.twitch.tv/helix/users/follows?to_id=' + to_id + '&from_id=' + from_id
            r = requests.get(url_follow, headers=headers).json()
            print(json.dumps(r, indent=4, sort_keys=True))
            try:
                f = r['data'][0]['followed_at']
                con_followed_at = datetime.datetime.strptime(f, '%Y-%m-%dT%H:%M:%SZ')
                time = relativedelta(datetime.datetime.now(), con_followed_at)
                string = ctx.author.name + ' has been following for '
                if time.years == 1:
                    string += str(time.years) + ' year, '
                elif time.years > 1:
                    string += str(time.years) + ' years, '
                if time.months == 1:
                    string += str(time.months) + ' month, '
                elif time.months > 1:
                    string += str(time.months) + ' months, '
                if time.days == 1:
                    string += str(time.days) + ' day, '
                elif time.days > 1:
                    string += str(time.days) + ' days, '
                if time.hours == 1:
                    string += str(time.hours) + ' hour '
                elif time.hours > 1:
                    string += str(time.hours) + ' hours '
                print(self.nick + ': ' + string)
                await ctx.send(string)
            except Exception as e:
                print(e)
                print(self.nick + ': ' + ctx.author.name + ' is not following')
                await ctx.send(ctx.author.name + ' is not following')

    @commands.command()
    async def ai(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['ai_enabled'] == 'True':

            response = self.ai_complete(ctx.message.content.split(' ', 1)[1])

            try:
                print(self.nick + ': ' + response.choices[0].text.strip())
                await ctx.send(response.choices[0].text.strip().replace('\r', ' ').replace('\n', ' ')[:500])
            except AttributeError as e:
                print(self.nick + ': ' + response)
                await ctx.send(response)

    @commands.command()
    async def define(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['define_enabled'] == 'True':
            config = configparser.ConfigParser()
            config.read(r'keys.ini')
            url = 'https://www.dictionaryapi.com/api/v3/references/learners/json/' + ctx.message.content.split(' ', 1)[
                1] + '?key=' + config['keys']['merriamwebster_api_key']
            r = requests.get(url).json()
            # print(json.dumps(r, indent=4, sort_keys=True))
            try:
                definition = str(r[0]['shortdef'][0])
                print(self.nick + ': ' + definition)
                await ctx.send(definition[:500])
            except TypeError as e:
                print(self.nick + ': Definition for ' + ctx.message.content.split(' ', 1)[1] + ' not found.')
                await ctx.send('Definition for ' + ctx.message.content.split(' ', 1)[1] + ' not found.')

    @commands.command()
    async def translate(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['translate_enabled'] == 'True':
            translated = GoogleTranslator(source='auto', target='en').translate(ctx.message.content.split(' ', 1)[1])
            language_short = single_detection(ctx.message.content.split(' ', 1)[1], api_key=config['keys'][
                'detect_language_api_key'])
            language_long = pycountry.languages.get(alpha_2=language_short)
            response = 'From ' + language_long.name + ': ' + translated
            print(self.nick + ': ' + response)
            await ctx.send(response[:500])

    @commands.command()
    async def weather(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['weather_enabled'] == 'True':
            owm = OWM(config['keys']['owm_api_key'])
            mgr = owm.weather_manager()
            try:
                # F = 1.8(K - 273) + 32
                # C = K – 273.15
                g = geocoders.GoogleV3(api_key=config['keys']['google_api_key'], domain='maps.googleapis.com')
                observation = mgr.weather_at_place(ctx.message.content.split(' ', 1)[1])
                one_call = mgr.one_call(lat=observation.location.lat, lon=observation.location.lon)
                place_object = g.reverse((observation.location.lat, observation.location.lon))
                # print(json.dumps(place_object.raw, indent=4, sort_keys=True))

                city = ''
                state = ''
                country = ''
                plus_code = ''

                for item in place_object.raw['address_components']:
                    if 'locality' in item['types']:
                        city = item['long_name']
                    if 'administrative_area_level_1' in item['types']:
                        state = item['short_name']
                    if 'country' in item['types']:
                        country = item['short_name']
                    if 'plus_code' in item['types']:
                        plus_code = item['short_name']

                place = ''
                if city != '':
                    place += city + ', '
                if state != '':
                    place += state + ', '
                if country != '':
                    place += country
                if place == '':
                    place += plus_code

                temp_f = int(1.8 * (observation.weather.temp['temp'] - 273) + 32)
                temp_c = int(observation.weather.temp['temp'] - 273.15)
                f_temp_f = int(one_call.forecast_daily[1].temperature('fahrenheit').get('max', None))
                f_temp_c = int(one_call.forecast_daily[1].temperature('celsius').get('max', None))
                print(self.nick + ': The temperature in ' + place + ' is ' + str(temp_f) + '°F (' + str(
                    temp_c) + '°C) and ' + observation.weather.detailed_status
                      + ', Tomorrow: ' + str(f_temp_f) + '°F (' + str(f_temp_c) + '°C) and ' + one_call.forecast_daily[
                          1].detailed_status)
                await ctx.send('The temperature in ' + place + ' is ' + str(temp_f) + '°F (' + str(
                    temp_c) + '°C) and ' + observation.weather.detailed_status
                               + ', Tomorrow: ' + str(f_temp_f) + '°F (' + str(f_temp_c) + '°C) and ' +
                               one_call.forecast_daily[1].detailed_status)
            except Exception as e:
                print(e)
                print(self.nick + ': Location ' + ctx.message.content.split(' ', 1)[1] + ' not found.')
                await ctx.send('Location ' + ctx.message.content.split(' ', 1)[1] + ' not found.')

    @commands.command()
    async def reddit(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['reddit_enabled'] == 'True':
            joke = self.reddit_get()
            q = queue.Queue()
            x = threading.Thread(target=self.reddit_confirm, args=('Confirm?',joke, q))
            x.start()
            while x.is_alive():
                await asyncio.sleep(0)
            result = q.get()
            if result:
                print(self.nick + ': ' + joke)
                await ctx.send(joke)

    @commands.command()
    async def help(self, ctx: commands.Context):
        output = 'Enabled Commands Are: '
        config = configparser.ConfigParser()
        config.read(r'keys.ini')

        if config['options']['wiki_enabled'] == 'True':
            output += '!wiki '
        if config['options']['followage_enabled'] == 'True':
            output += '!followage '
        if config['options']['ai_enabled'] == 'True':
            output += '!ai '
        if config['options']['define_enabled'] == 'True':
            output += '!define '
        if config['options']['translate_enabled'] == 'True':
            output += '!translate '
        if config['options']['weather_enabled'] == 'True':
            output += '!weather '
        if config['options']['reddit_enabled'] == 'True':
            output += '!reddit '
        if config['options']['time_enabled'] == 'True':
            output += '!time '
        if config['options']['exchange_enabled'] == 'True':
            output += '!exchange '
        if config['options']['fact_enabled'] == 'True':
            output += '!fact '

        print(self.nick + ': ' + output)
        await ctx.send(output)

    @commands.command()
    async def time(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['time_enabled'] == 'True':
            g = geocoders.GoogleV3(api_key=config['keys']['google_api_key'], domain='maps.googleapis.com')
            place, (lat, lng) = g.geocode(ctx.message.content.split(' ', 1)[1])
            tz = g.reverse_timezone((lat, lng))
            tz_object = timezone(str(tz))
            newtime = datetime.datetime.now(tz_object)
            print(self.nick + ': The current time in ' + place + ' is ' + newtime.strftime('%#I:%M %p'))
            await ctx.send('The current time in ' + place + ' is ' + newtime.strftime('%#I:%M %p'))

    @commands.command()
    async def exchange(self, ctx: commands.Context, cur_from='usd', cur_to='eur', amount='1'):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['exchange_enabled'] == 'True':
            url = 'https://api.exchangerate.host/convert?from=' + cur_from + '&to=' + cur_to + '&amount=' + amount
            data = requests.get(url).json()
            print(self.nick + ': ' + amount + ' ' + cur_from + ' = ' + str(data['result']) + ' ' + cur_to)
            await ctx.send(amount + ' ' + cur_from + ' = ' + str(data['result']) + ' ' + cur_to)

    @commands.command()
    async def fact(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['fact_enabled'] == 'True':
            url = 'https://uselessfacts.jsph.pl/random.json?language=en'
            fact = requests.get(url).json()
            # print(json.dumps(fact, indent=4, sort_keys=True))
            print(self.nick + ': ' + fact['text'])
            await ctx.send(fact['text'])

    @staticmethod
    def reddit_confirm(title, message, q):
        q.put(tkinter.messagebox.askyesno(title, message))

    @staticmethod
    def ai_complete(message):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        completion = openai.Completion.create(temperature=float(config['options']['temperature']),
                                              max_tokens=int(config['options']['tokens']),
                                              engine=config['options']['ai_engine'],
                                              prompt=message)
        print(json.dumps(completion, indent=4, sort_keys=True))
        moderation = openai.Moderation.create(input=completion.choices[0].text, model='text-moderation-stable')
        print(json.dumps(moderation, indent=4, sort_keys=True))

        if not moderation.results[0]['flagged']:
            return completion
        else:
            return 'Response Flagged'

    @staticmethod
    def getjoke(url):
        headers = {'User-agent': 'pywiki'}
        r = requests.get(url, headers=headers).json()
        joke = ''
        while joke == '':
            post = r['data']['children'][random.randint(0, len(r['data']['children']) - 1)]
            # print(json.dumps(title, indent=4, sort_keys=True))
            subreddit = post['data']['subreddit']
            title = post['data']['title']
            output = post['data']['selftext']
            if (len(output) < 100 and not
            re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', output)):
                if (title.endswith('?') or
                        title.endswith('.') or
                        title.endswith('…') or
                        title.endswith(',') or
                        len(output) == 0):
                    text = title + ' '
                else:
                    text = title + '…'
                joke = text + output.replace('\r', ' ').replace('\n', ' ')
                joke = re.split("edit:", joke, flags=re.IGNORECASE)[0] + ' r/' + subreddit
            else:
                print(title + ' ' + output + ' r/' + subreddit)
                print('regexed')
        return joke

    def reddit_get(self, *args):
        random.seed()
        headers = {'User-agent': 'pywiki'}

        headlines = []

        config = configparser.ConfigParser()
        config.read(r'keys.ini')

        urls = json.loads(config.get('variables', 'reddit_urls'))

        random.shuffle(urls)

        headlines.append(self.getjoke(urls[0]))

        random.shuffle(headlines)
        return headlines[0]


def main():
    try:
        bot = Bot()
        bot.run()
    finally:
        sys.exit()


if __name__ == '__main__':
    main()
