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

class Bot(commands.Bot):

    def __init__(self):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        super().__init__(token=config['keys']['token'], prefix='!', initial_channels=config['options']['channel'].split(','))
        self.client_id = config['keys']['client_id']
        self.client_secret = config['keys']['client_secret']
        self.client_credentials = requests.post('https://id.twitch.tv/oauth2/token?client_id='
                                            + self.client_id
                                            + '&client_secret='
                                            + self.client_secret
                                            + '&grant_type=client_credentials'
                                            + '&scope='
                                            + '').json()
        print(json.dumps(self.client_credentials, indent=4, sort_keys=True))
        self.wiki_cooldown = False
        openai.api_key = config['keys']['openai_api_key']
        #engines = openai.Engine.list()
        #print(engines.data)

    async def event_ready(self):
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')

    async def event_message(self, message):
        if message.echo:
            return
        
        print(message.author.name + ': ' + message.content)
        
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if message.author.name not in config['variables']['chatters'].split(','):
            config['variables']['chatters'] += message.author.name + ','
            with open('keys.ini', 'w') as configfile:
                config.write(configfile)
            print(self.nick + ': Welcome ' + message.author.name + '!')
            await message.channel.send('Welcome ' + message.author.name + '!')
            
        await self.handle_commands(message)

    @routines.routine(iterations=1)
    async def wiki_cooldown_routine(self):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        countdown = int(config['options']['wiki_cooldown'])
        while countdown != 0:
            await asyncio.sleep(1)
            print(countdown,end=" ")
            countdown-=1
        self.wiki_cooldown = False

    @commands.command()
    async def wiki(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['wiki_enabled'] == 'True':
            if self.wiki_cooldown == False:
                wikipedia.set_lang("en")

                try:
                    try:
                        p = wikipedia.summary(ctx.message.content.split(' ', 1)[1], sentences=2, auto_suggest=False)
                    except wikipedia.DisambiguationError as e:
                        print('\n'.join('{}: {}'.format(*k) for k in enumerate(e.options)))
                        p = wikipedia.summary(str(e.options[0]), sentences=2, auto_suggest=False)
                except:
                    try:
                        p = wikipedia.summary(ctx.message.content.split(' ', 1)[1], sentences=2, auto_suggest=True)
                    except wikipedia.DisambiguationError as e:
                        print('\n'.join('{}: {}'.format(*k) for k in enumerate(e.options)))
                        p = wikipedia.summary(str(e.options[0]), sentences=2, auto_suggest=False)
                    except wikipedia.PageError as e:
                        p = str(e)
                    
                print(self.nick + ": " + p)
                await ctx.send(p.replace('\r','').replace('\n','')[:500])
                self.wiki_cooldown = True
                self.wiki_cooldown_routine.start()

    @commands.command()
    async def followage(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['followage_enabled'] == 'True':
            headers = {'Client-ID': self.client_id, 'Authorization':'Bearer ' + self.client_credentials['access_token']}
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
                print(self.nick + ': ' + string + 'patche5Love')
                await ctx.send(string + 'patche5Love')
            except Exception as e:
                print(e)
                print(self.nick + ': ' + ctx.author.name + ' is not following')
                await ctx.send(ctx.author.name + ' is not following')

    @commands.command()
    async def ai(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['ai_enabled'] == 'True':
            completion = openai.Completion.create(max_tokens = 128, engine='text-davinci-002', prompt=ctx.message.content.split(' ', 1)[1])
            print(self.nick + ': ' + completion.choices[0].text.strip())
            await ctx.send(completion.choices[0].text.strip().replace('\r',' ').replace('\n',' ')[:500])

    @commands.command()
    async def define(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['define_enabled'] == 'True':
            config = configparser.ConfigParser()
            config.read(r'keys.ini')
            url =  'https://www.dictionaryapi.com/api/v3/references/learners/json/' + ctx.message.content.split(' ', 1)[1] + '?key=' + config['keys']['merriamwebster_api_key']
            r = requests.get(url).json()
            #print(json.dumps(r, indent=4, sort_keys=True))
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
            print(self.nick + ': ' + translated)
            await ctx.send(translated[:500])
                
    @commands.command()
    async def weather(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['weather_enabled'] == 'True':
            config = configparser.ConfigParser()
            config.read(r'keys.ini')
            owm = OWM(config['keys']['owm_api_key'])
            mgr = owm.weather_manager()
            try:
                observation = mgr.weather_at_place(ctx.message.content.split(' ', 1)[1])
                #F = 1.8(K - 273) + 32
                #C = K – 273.15
                temp_f = int(1.8 * (observation.weather.temp['temp'] - 273) + 32)
                temp_c = int(observation.weather.temp['temp'] - 273.15)
                print(self.nick + ': The temperture in ' + observation.location.name + ' is ' + str(temp_f) + '°F (' + str(temp_c) + '°C) and ' + observation.weather.status)
                await ctx.send('The temperture in ' + observation.location.name + ' is ' + str(temp_f) + '°F (' + str(temp_c) + '°C) and ' + observation.weather.status)
            except:
                print(self.nick + ': Location ' + ctx.message.content.split(' ', 1)[1] + ' not found.')
                await ctx.send('Location ' + ctx.message.content.split(' ', 1)[1] + ' not found.')
            
    @commands.command()
    async def reddit(self, ctx: commands.Context):
        config = configparser.ConfigParser()
        config.read(r'keys.ini')
        if config['options']['reddit_enabled'] == 'True':
            joke = self.reddit_get()
            print(self.nick + ': ' + joke)
            await ctx.send(joke)

    @commands.command()
    async def help(self, ctx: commands.Context):
        output = ''
        for key in self.commands:
            output += self._prefix + key + ' '
        print(self.nick + ': ' + output)
        await ctx.send(output)

    def getjoke(self, url):
        headers = {'User-agent': 'pywiki'}
        r = requests.get(url, headers=headers).json()
        joke = ''
        while joke == '':
            post = r['data']['children'][random.randint(0,len(r['data']['children'])-1)]
            #print(json.dumps(title, indent=4, sort_keys=True))
            subreddit = post['data']['subreddit']
            title = post['data']['title']
            output = post['data']['selftext']
            #print(title + ' ' + output + ' r/' + subreddit)
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
                joke = text + output.replace('\r',' ').replace('\n',' ') + ' r/' + subreddit
                joke = re.split("edit:", joke, flags=re.IGNORECASE)[0]
            else:
                print ('regexed')
        return joke
    
    def reddit_get(self, *args):
        random.seed()            
        headers = {'User-agent': 'pywiki'}

        headlines = []
        
        config = configparser.ConfigParser()
        config.read(r'keys.ini')

        urls = json.loads(config.get('variables','reddit_urls'))
        
        random.shuffle(urls)

        headlines.append(self.getjoke(urls[0]))
                
        random.shuffle(headlines)
        return(headlines[0])

bot = Bot()
bot.run()
