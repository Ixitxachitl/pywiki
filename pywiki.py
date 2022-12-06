import asyncio
import atexit
import configparser
import ctypes
import datetime
import io
import json
import os
import queue
import random
import re
import sys
import threading
import urllib.parse
from html import unescape
from os import path
from pprint import pprint

import lyricsgenius
import openai
import py2snes
import pycountry
import pyttsx3
import requests
import wikipedia
from PIL import Image
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from deep_translator import GoogleTranslator
from deep_translator import single_detection
from fuzzywuzzy import fuzz
from geopy import geocoders
from imdb import Cinemagoer
from pyowm.owm import OWM
from pytz import timezone
from rich import print as rprint
from twitchio.ext import commands
from twitchio.ext import pubsub
from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation
from imgur_python import Imgur


class Bot(commands.Bot):
    config = configparser.ConfigParser()
    config.read(r'keys.ini')

    def __init__(self):
        self.prefix = '!'
        super().__init__(token=self.config['keys']['token'], prefix=self.prefix,
                         initial_channels=self.config['options']['channel'].split(','),
                         client_id=self.config['keys']['client_id'],
                         client_secret=self.config['keys']['client_secret'],
                         case_insensitive=True)
        self.client_id = self.config['keys']['client_id']
        self.client_secret = self.config['keys']['client_secret']
        self.client_credentials = requests.post('https://id.twitch.tv/oauth2/token?client_id='
                                                + self.client_id
                                                + '&client_secret='
                                                + self.client_secret
                                                + '&grant_type=client_credentials'
                                                + '&scope='
                                                + '').json()
        # print(json.dumps(self.client_credentials, indent=4, sort_keys=True))
        openai.api_key = self.config['keys']['openai_api_key']
        # engines = openai.Engine.list()
        # print(engines.data)

        self.ia = Cinemagoer()

        self.genius = lyricsgenius.Genius(self.config['keys']['genius_access_token'])

        self.my_token = self.config['keys']['token']
        self.users_oauth_token = self.config['keys']['pubsub_oauth_token']

        self.oxford_app_id = self.config['keys']['oxford_application_id']
        self.oxford_api_key = self.config['keys']['oxford_api_key']

        if self.config['options']['dream_enabled'] == 'True':
            os.environ['STABILITY_HOST'] = 'grpc.stability.ai:443'
            os.environ['STABILITY_KEY'] = self.config['keys']['stability_key']
            self.stability_api = client.StabilityInference(
                key=os.environ['STABILITY_KEY'],  # API Key reference.
                verbose=True,  # Print debug messages.
                engine='stable-diffusion-512-v2-0',
            )

        self.imgur_client = Imgur({'client_id': self.config['keys']['imgur_client_id'],
                                   'client_secret': self.config['keys']['imgur_client_secret'],
                                   'access_token': self.config['keys']['imgur_access_token'],
                                   'refresh_token': self.config['keys']['imgur_refresh_token']})

        self.keysig = {
            'c': {
                'major': 'none',
                'minor': 'B♭, E♭, A♭'
            },
            'c sharp': {
                'major': 'F♯, C♯, G♯, D♯, A♯, E♯, B♯',
                'minor': 'F♯, C♯, G♯, D♯'
            },
            'd flat': {
                'major': 'B♭, E♭, A♭, D♭, G♭',
                'minor': 'F♯, C♯, G♯, D♯'
            },
            'd': {
                'major': 'F♯, C♯',
                'minor': 'B♭'
            },
            'd sharp': {
                'minor': 'F♯, C♯, G♯, D♯, A♯, E♯'
            },
            'e flat': {
                'major': 'B♭, E♭, A♭',
                'minor': 'B♭, E♭, A♭, D♭, G♭, C♭'
            },
            'e': {
                'major': 'F♯, C♯, G♯, D♯',
                'minor': 'F♯'
            },
            'f': {
                'major': 'B♭',
                'minor': 'B♭, E♭, A♭, D♭'
            },
            'f sharp': {
                'major': 'F♯, C♯, G♯, D♯, A♯, E♯',
                'minor': 'B♭, E♭, A♭, D♭'
            },
            'g flat': {
                'major': 'B♭, E♭, A♭, D♭, G♭, C♭',
            },
            'g': {
                'major': 'F♯',
                'minor': 'B♭, E♭'
            },
            'g sharp': {
                'minor': 'F♯, C♯, G♯, D♯, A♯'
            },
            'a flat': {
                'major': 'B♭, E♭, A♭, D♭',
                'minor': 'B♭, E♭, A♭, D♭, G♭, C♭, F♭'
            },
            'a': {
                'major': 'F♯, C♯, G♯',
                'minor': 'none'
            },
            'a sharp': {
                'minor': 'F♯, C♯, G♯, D♯, A♯, E♯, B♯'
            },
            'b flat': {
                'major': 'B♭, E♭',
                'minor': 'B♭, E♭, A♭, D♭, G♭'
            },
            'b': {
                'major': 'F♯, C♯, G♯, D♯, A♯',
                'minor': 'F♯, C♯'
            },
            'c flat': {
                'major': 'B♭, E♭, A♭, D♭, G♭, C♭, F♭'
            }
        }

        self.snes_connected = False

        self.trivia_guesses = {}

        if self.config['options']['snes_enabled'] == 'True':
            self.snes = py2snes.snes()

        if self.config['options']['pubsub_enabled'] == 'True':
            self.users_channel = self.config['options']['pubsub_channel']

            headers = {'Client-ID': self.client_id,
                       'Authorization': 'Bearer ' + self.client_credentials['access_token']}
            url = 'https://api.twitch.tv/helix/users?login=' + self.users_channel
            self.users_channel_id = int(requests.get(url, headers=headers).json()['data'][0]['id'])

            self.pubsub = pubsub.PubSubPool(self)
            self.topics = [pubsub.channel_points(self.users_oauth_token)[self.users_channel_id]]

    async def event_pubsub_channel_points(self, event: pubsub.PubSubChannelPointsMessage):
        # print(json.dumps(event._data, indent=4, sort_keys=True))
        channel_name = await self.fetch_channels([event.channel_id])
        channel = self.get_channel(channel_name[0].user.name)
        event_id = event.reward.title

        # # #---EDIT HERE FOR CUSTOM REDEMPTIONS---# # #
        if event_id == 'Eggs':
            await channel.send('🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚'
                               '🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚🥚')
        elif event_id == 'TTS':
            user_input = event.input
            pyttsx3.speak(user_input)
        elif event_id == "Mushroom":
            if self.snes_connected:
                await self.snes.PutAddress([(int('0xF50019', 16), [int('0x01', 16)])])
            await channel.send('🍄')
        elif event_id == "Cape":
            if self.snes_connected:
                await self.snes.PutAddress([(int('0xF50019', 16), [int('0x02', 16)])])
            await channel.send('🪶')
        elif event_id == "Fire Flower":
            if self.snes_connected:
                await self.snes.PutAddress([(int('0xF50019', 16), [int('0x03', 16)])])
            await channel.send('🌹')
        elif event_id == 'Random Fact':
            fact_url = 'https://uselessfacts.jsph.pl/random.json?language=en'
            fact = requests.get(fact_url).json()
            # print(json.dumps(fact, indent=4, sort_keys=True))
            await channel.send(fact['text'])
        elif event_id == 'AI':
            response = self.ai_complete(self, event.input)

            if hasattr(response, 'choices'):
                response.choices[0].text = response.choices[0].text.strip().replace('\r', ' ').replace('\n', ' ')
                response.choices[0].text = ' '.join(re.split(r'(?<=[.:;])\s', response.choices[0].text)[:3])
                while response.choices[0].text.startswith('.') or response.choices[0].text.startswith('/'):
                    response.choices[0].text = response.choices[0].text[1:]
                await channel.send(response.choices[0].text[:500])
            else:
                await channel.send(response)
        elif event_id == 'Image Generator':
            try:
                self.config['keys']['imgur_access_token'] = self.imgur_client.access_token()['response']['access_token']
                with open('keys.ini', 'w') as configfile:
                    self.config.write(configfile)
                self.imgur_client = Imgur({'client_id': self.config['keys']['imgur_client_id'],
                                           'client_secret': self.config['keys']['imgur_client_secret'],
                                           'access_token': self.config['keys']['imgur_access_token'],
                                           'refresh_token': self.config['keys']['imgur_refresh_token']})
                image = openai.Image.create(prompt=event.input,
                                            n=1,
                                            size="512x512")
                img_data = requests.get(image['data'][0]['url']).content
                with open(str(image['created']) + '.png', 'wb') as handler:
                    handler.write(img_data)
                response = \
                    self.imgur_client.image_upload(path.relpath('./' + str(image['created']) + '.png'),
                                                   str(image['created']), event.input)
                await channel.send(response['response']['data']['link'])
            except openai.error.OpenAIError as e:
                await channel.send(e.error.message)
        elif event_id == 'Trivia' and channel.name not in self.trivia_guesses:
            self.trivia_guesses.update({channel.name: {}})
            fast = False
            bot_chatter = channel.get_chatter(self.nick)
            if bot_chatter.is_mod or bot_chatter.is_vip:
                fast = True
            url = self.config['variables']['trivia_url']
            trivia_object = requests.get(url).json()
            # print(json.dumps(trivia_object, indent=4, sort_keys=True))
            answers = trivia_object['results'][0]['incorrect_answers']
            answers.append(trivia_object['results'][0]['correct_answer'])
            random.shuffle(answers)
            index = ['(A)', '(B)', '(C)', '(D)']
            index2 = ['a', 'b', 'c', 'd']
            number = 0
            correct_answer = ''
            await channel.send(unescape(trivia_object['results'][0]['question']))
            if not fast:
                await asyncio.sleep(2)
            for answer in answers:
                if answer == trivia_object['results'][0]['correct_answer']:
                    correct_answer = index2[number]
                answer = index[number] + ' ' + answer
                await channel.send(unescape(answer))
                number += 1
                if not fast:
                    await asyncio.sleep(2)
            await asyncio.sleep(30)
            await channel.send('The correct answer was (' + correct_answer.upper() + ') ' +
                               unescape(trivia_object['results'][0]['correct_answer']))
            if not fast:
                await asyncio.sleep(2)
            winners = 'Winners: '
            with open('winners.json', encoding='utf8') as infile:
                winner_list = json.load(infile)
            for key in self.trivia_guesses[channel.name]:
                if self.trivia_guesses[channel.name][key] == correct_answer:
                    if channel.name not in winner_list:
                        winner_list.update({channel.name: {}})
                    if key in winner_list[channel.name]:
                        winner_list[channel.name].update({key: winner_list[channel.name][key] + 1})
                    else:
                        winner_list[channel.name].update({key: 1})
                    with open('winners.json', 'w') as outfile:
                        json.dump(winner_list, outfile)
                    winners += key + ' '
            if winners != 'Winners: ':
                await channel.send(winners)
            else:
                await channel.send('Nobody Won')
            self.trivia_guesses.pop(channel.name)

        '''
        elif event_id == 'Echo':
            await channel.send(event.input)
        '''
        # # #---END EDIT ZONE---# # #

    async def snes_connect(self):
        await self.snes.connect()
        devices = await self.snes.DeviceList()
        print(devices)
        try:
            await self.snes.Attach(devices[0])
            print(await self.snes.Info())
            self.snes_connected = True
        except Exception as e:
            print(str(e) + ' SD2SNES Not Detected')
            self.snes_connected = False

    async def event_ready(self):
        self.config.read(r'keys.ini')

        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')

        if self.config['options']['snes_enabled'] == 'True':
            await self.snes_connect()
        if self.config['options']['pubsub_enabled'] == 'True':
            await self.pubsub.subscribe_topics(self.topics)
            rprint('[bold green]Pubsub Ready[/]')

    async def event_channel_joined(self, channel):
        print('Joined ' + channel.name)

    async def event_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            rprint('[bold red]' + str(error) + '[/]')
            retry = relativedelta(seconds=error.retry_after)
            await ctx.send('@' + ctx.message.author.name + ' This command is on cooldown, you can use it in ' +
                           str(int(retry.hours)) + ':' + str(int(retry.minutes)) + ':' + str(int(retry.seconds)))
        elif isinstance(error, commands.CommandNotFound):
            rprint('[bold red]' + error.args[0] + '[/]')
        elif isinstance(error, commands.MissingRequiredArgument):  # Doesn't work
            rprint('[bold red]' + error.args[0] + '[/]')
        else:
            raise error

    async def event_message(self, message):
        if message.echo:
            channel = message.channel
            bot_chatter = channel.get_chatter(self.nick)
            bot_user = await self.fetch_users([bot_chatter.name])
            bot_color = await self.fetch_chatters_colors([bot_user[0].id])
            if bot_color[0].color is not None:
                start_color = '[bold ' + bot_color[0].color + ']'
                end_color = '[/]'
                author = bot_user[0].display_name
                if bot_chatter.is_subscriber:
                    author = '✨' + author
                if bot_chatter.is_vip:
                    author = '💎' + author
                if bot_chatter.is_mod:
                    author = '🗡️' + author
                if bot_chatter.is_broadcaster:
                    author = '🎥️' + author
                rprint(start_color + author + end_color + ': ' + message.content)
            else:
                print(message.author.name + ': ' + message.content)
            return

        if message.author.name == self.nick:
            return

        start_color = '[bold ' + message.author.color + ']'
        end_color = '[/]'
        author = message.author.display_name
        if message.author.is_subscriber:
            author = '✨' + author
        if message.author.is_vip:
            author = '💎' + author
        if message.author.is_mod:
            author = '🗡️' + author
        if message.author.is_broadcaster:
            author = '🎥️' + author
        rprint(start_color + author + end_color + ': ' + message.content)

        self.config.read(r'keys.ini')

        chatters = json.loads(self.config.get('variables', 'chatters'))
        if message.author.name not in chatters:
            chatters.append(message.author.name)
            self.config['variables']['chatters'] = json.dumps(chatters)
            with open('keys.ini', 'w') as configfile:
                self.config.write(configfile)
            if self.config['options']['welcome_enabled'] == 'True':

                for key in self.config['greetings']:
                    if message.author.name == key.lower():
                        response = self.config['greetings'][key]
                        await message.channel.send(response)
                        break

        if message.channel.name in self.trivia_guesses:
            if message.content.lower() == 'a' or \
                    message.content.lower() == 'b' or \
                    message.content.lower() == 'c' or \
                    message.content.lower() == 'd':
                self.trivia_guesses[message.channel.name].update({message.author.name: message.content.lower()})
                # print(str(self.trivia_guesses[message.channel.name]))

        await self.handle_commands(message)

    @commands.command()
    async def settitle(self, ctx: commands.Context, *, args=None):
        if ctx.message.author.is_broadcaster or ctx.message.author.is_mod and self.users_channel == ctx.channel.name:
            if args is None:
                await ctx.send('Please provide an input text')
            else:
                user = await self.fetch_users([ctx.channel.name])
                url = 'https://api.twitch.tv/helix/channels?broadcaster_id=' + str(user[0].id)
                headers = {'Authorization': 'Bearer ' + self.users_oauth_token,
                           'Client-ID': self.client_id,
                           'Content-Type': 'application/json'}
                data = {'title': args}
                response = requests.patch(url=url, headers=headers, data=json.dumps(data))
                # await user[0].modify_stream(token=self.users_oauth_token, title=args) #proper way to do it doesn't
                #                                                                        find client id?
                if response.status_code == 204:
                    await ctx.send('Set title to: ' + args)
                else:
                    await ctx.send('There was an error setting the title: ' + str(response.status_code))

    @commands.command()
    async def setgame(self, ctx: commands.Context, *, args=None):
        if ctx.message.author.is_broadcaster or ctx.message.author.is_mod and self.users_channel == ctx.channel.name:
            user = await self.fetch_users([ctx.channel.name])
            if args is not None:
                game = await self.fetch_games(names=[args])
                game_id = game[0].id
                data = {'game_id': str(game_id)}
            else:
                class GameObject(dict):
                    name = "Nothing"

                game = [GameObject()]
                data = {'game_id': '0'}
            url = 'https://api.twitch.tv/helix/channels?broadcaster_id=' + str(user[0].id)
            headers = {'Authorization': 'Bearer ' + self.users_oauth_token,
                       'Client-ID': self.client_id,
                       'Content-Type': 'application/json'}

            response = requests.patch(url=url, headers=headers, data=json.dumps(data))
            if response.status_code == 204:
                await ctx.send('Set game to: ' + game[0].name)
            else:
                await ctx.send('There was an error setting the game: ' + str(response.status_code))

    @commands.cooldown(rate=1, per=float(config['options']['wiki_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def wiki(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['wiki_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide an input text')
            else:
                wikipedia.set_lang("en")
                try:
                    try:
                        p = wikipedia.summary(args, sentences=3, auto_suggest=False)
                    except wikipedia.DisambiguationError as e:
                        print('\n'.join('{}: {}'.format(*k) for k in enumerate(e.options)))
                        p = wikipedia.summary(str(e.options[0]), sentences=3, auto_suggest=False)
                except Exception as e:
                    print(e)
                    try:
                        p = wikipedia.summary(args, sentences=3, auto_suggest=True)
                    except wikipedia.DisambiguationError as e:
                        print('\n'.join('{}: {}'.format(*k) for k in enumerate(e.options)))
                        p = wikipedia.summary(str(e.options[0]), sentences=3, auto_suggest=False)
                    except wikipedia.PageError as e:
                        p = str(e)
                await ctx.send(p.replace('\r', '').replace('\n', '')[:500])

    @commands.cooldown(rate=1, per=float(config['options']['uptime_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def uptime(self, ctx: commands.Context):
        self.config.read(r'keys.ini')
        if self.config['options']['uptime_enabled'] == 'True':
            channel = await self.fetch_users([ctx.channel.name])
            stream = await self.fetch_streams([channel[0].id])
            try:
                started_at = stream[0].started_at.strftime('%Y-%m-%dT%H:%M:%SZ')
                con_started_at = datetime.datetime.strptime(started_at, '%Y-%m-%dT%H:%M:%SZ')
                uptime = relativedelta(datetime.datetime.utcnow(), con_started_at)
                string = ''
                if uptime.hours == 1:
                    string += str(uptime.hours) + ' hour '
                elif uptime.hours > 1:
                    string += str(uptime.hours) + ' hours '
                if uptime.minutes == 1:
                    string += str(uptime.minutes) + ' minute '
                elif uptime.minutes > 1:
                    string += str(uptime.minutes) + ' minutes '
                await ctx.send(channel[0].display_name + ' has been live for ' + string)
            except Exception as e:
                print(e)
                await ctx.send(channel[0].display_name + ' is not live')

    @commands.cooldown(rate=1, per=float(config['options']['followage_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def followage(self, ctx: commands.Context):
        self.config.read(r'keys.ini')
        if self.config['options']['followage_enabled'] == 'True':

            from_user = await self.fetch_users([ctx.message.author.name])
            to_user = await self.fetch_users([ctx.message.channel.name])

            follow = await from_user[0].fetch_follow(to_user[0])

            try:
                f = follow.followed_at.strftime('%Y-%m-%dT%H:%M:%SZ')
                con_followed_at = datetime.datetime.strptime(f, '%Y-%m-%dT%H:%M:%SZ')
                follow_time = relativedelta(datetime.datetime.utcnow(), con_followed_at)
                string = ctx.author.display_name + ' has been following for '
                if follow_time.years == 1:
                    string += str(follow_time.years) + ' year '
                elif follow_time.years > 1:
                    string += str(follow_time.years) + ' years '
                if follow_time.months == 1:
                    string += str(follow_time.months) + ' month '
                elif follow_time.months > 1:
                    string += str(follow_time.months) + ' months '
                if follow_time.days == 1:
                    string += str(follow_time.days) + ' day '
                elif follow_time.days > 1:
                    string += str(follow_time.days) + ' days '
                if follow_time.hours == 1:
                    string += str(follow_time.hours) + ' hour '
                elif follow_time.hours > 1:
                    string += str(follow_time.hours) + ' hours '
                await ctx.send(string)
            except Exception as e:
                print(e)
                await ctx.send(ctx.author.display_name + ' is not following')

    @commands.cooldown(rate=1, per=float(config['options']['key_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def key(self, ctx: commands.Context, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['key_enabled'] == 'True':
            if args is None:
                await ctx.send('Syntax Error')
            else:
                try:
                    if len(ctx.message.content.split(' ', 1)) != 2:
                        raise Exception('Syntax Error')
                    key_index = ''
                    command = args
                    if len(command) == 2:
                        if command[1] == '#':
                            key_index = command[0].lower() + ' sharp'
                        if command[1] == 'b':
                            key_index = command[0].lower() + ' flat'
                    elif len(command) == 1:
                        key_index = command[0].lower()
                    else:
                        raise Exception('Syntax Error')

                    if key_index in self.keysig:
                        if command[0].isupper():
                            if 'major' in self.keysig[key_index]:
                                await ctx.send(self.keysig[key_index]['major'])
                            else:
                                raise Exception('Syntax Error')
                        else:
                            if 'minor' in self.keysig[key_index]:
                                await ctx.send(self.keysig[key_index]['minor'])
                            else:
                                raise Exception('Syntax Error')
                    else:
                        raise Exception('Syntax Error')

                except Exception as e:
                    await ctx.send(str(e))

    @commands.cooldown(rate=1, per=float(config['options']['ai_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def ai(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['ai_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide an input text')
            else:
                response = self.ai_complete(self, args)

                if hasattr(response, 'choices'):
                    response.choices[0].text = response.choices[0].text.strip().replace('\r', ' ').replace('\n', ' ')
                    response.choices[0].text = ' '.join(re.split(r'(?<=[.:;])\s', response.choices[0].text)[:3])
                    while response.choices[0].text.startswith('.') or response.choices[0].text.startswith('/'):
                        response.choices[0].text = response.choices[0].text[1:]
                        print(response.choices[0].text)
                    await ctx.send(response.choices[0].text[:500])
                else:
                    await ctx.send(response)

    @commands.cooldown(rate=1, per=float(config['options']['imagine_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def imagine(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['imagine_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide an input text')
                ctx.command._cooldowns[0]._cache.update({(ctx.channel.name, ctx.message.author.id): (1, 0)})
            else:
                try:
                    self.config['keys']['imgur_access_token'] =\
                        self.imgur_client.access_token()['response']['access_token']
                    with open('keys.ini', 'w') as configfile:
                        self.config.write(configfile)
                    self.imgur_client = Imgur({'client_id': self.config['keys']['imgur_client_id'],
                                               'client_secret': self.config['keys']['imgur_client_secret'],
                                               'access_token': self.config['keys']['imgur_access_token'],
                                               'refresh_token': self.config['keys']['imgur_refresh_token']})
                    image = openai.Image.create(prompt=args,
                                                n=1,
                                                size="512x512")
                    img_data = requests.get(image['data'][0]['url']).content
                    with open(str(image['created']) + '.png', 'wb') as handler:
                        handler.write(img_data)
                    response = \
                        self.imgur_client.image_upload(path.relpath('./' + str(image['created']) + '.png'),
                                                       str(image['created']), args)
                    await ctx.send(response['response']['data']['link'])
                except openai.error.OpenAIError as e:
                    await ctx.send(e.error.message)
                    # # # This is super dirty
                    ctx.command._cooldowns[0]._cache.update({(ctx.channel.name, ctx.message.author.id): (1, 0)})
                    # # # Don't ever do this ^
                except TimeoutError as e:
                    await ctx.send(e)
                    ctx.command._cooldowns[0]._cache.update({(ctx.channel.name, ctx.message.author.id): (1, 0)})

    @commands.cooldown(rate=1, per=float(config['options']['dream_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def dream(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['dream_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide an input text')
                ctx.command._cooldowns[0]._cache.update({(ctx.channel.name, ctx.message.author.id): (1, 0)})
            else:
                try:
                    self.config['keys']['imgur_access_token'] =\
                        self.imgur_client.access_token()['response']['access_token']
                    with open('keys.ini', 'w') as configfile:
                        self.config.write(configfile)
                    self.imgur_client = Imgur({'client_id': self.config['keys']['imgur_client_id'],
                                               'client_secret': self.config['keys']['imgur_client_secret'],
                                               'access_token': self.config['keys']['imgur_access_token'],
                                               'refresh_token': self.config['keys']['imgur_refresh_token']})
                    answers = self.stability_api.generate(prompt=args,
                                                          sampler=generation.SAMPLER_K_DPMPP_2S_ANCESTRAL,
                                                          guidance_preset=generation.GUIDANCE_PRESET_FAST_GREEN)
                    for resp in answers:
                        for artifact in resp.artifacts:
                            if artifact.finish_reason == generation.FILTER:
                                print('Content Filtered, Try Again')
                                await ctx.send('Content Filtered, Try Again')
                                ctx.command._cooldowns[0]._cache.update(
                                    {(ctx.channel.name, ctx.message.author.id): (1, 0)})
                            if artifact.type == generation.ARTIFACT_IMAGE:
                                img = Image.open(io.BytesIO(artifact.binary))
                                img.save(str(artifact.seed) + '.png')
                                response = \
                                    self.imgur_client.image_upload(path.relpath('./' + str(artifact.seed) + '.png'),
                                                                   artifact.seed, args)
                                await ctx.send(response['response']['data']['link'])
                except Exception:
                    await ctx.send('Communication Error, Try Again')
                    ctx.command._cooldowns[0]._cache.update({(ctx.channel.name, ctx.message.author.id): (1, 0)})

    @commands.cooldown(rate=1, per=float(config['options']['define_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def define(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['define_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide an input text')
            else:
                language = 'en-us'
                word = args
                url = "https://od-api.oxforddictionaries.com:443/api/v2/entries/" + language + "/" + word.lower()
                headers = {"app_id": self.oxford_app_id, "app_key": self.oxford_api_key}
                r = requests.get(url, headers=headers).json()
                # print(json.dumps(r, indent=4, sort_keys=True))
                if 'results' in r:
                    definition = r['results'][0]['lexicalEntries'][0]['entries'][0]['senses'][0]['definitions'][0] \
                        .capitalize()
                    word = r['results'][0]['word'].capitalize()
                    category = r['results'][0]['lexicalEntries'][0]['lexicalCategory']['text']
                    pronunciation = \
                        r['results'][0]['lexicalEntries'][0]['entries'][0]['pronunciations'][0]['phoneticSpelling']
                    out = word + ' - ' + category + ' - ' + pronunciation + ': ' + definition
                else:
                    out = r['error']
                await ctx.send(out)

    @commands.cooldown(rate=1, per=float(config['options']['etymology_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def etymology(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['etymology_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide an input text')
            else:
                language = 'en-us'
                word = args
                url = "https://od-api.oxforddictionaries.com:443/api/v2/entries/" + language + "/" + word.lower()
                headers = {"app_id": self.oxford_app_id, "app_key": self.oxford_api_key}
                r = requests.get(url, headers=headers).json()
                if 'results' in r:
                    etymology = r['results'][0]['lexicalEntries'][0]['entries'][0]['etymologies'][0].capitalize()
                    word = r['results'][0]['word'].capitalize()

                    out = word + ': ' + etymology
                else:
                    out = r['error']
                await ctx.send(out)

    @commands.cooldown(rate=1, per=float(config['options']['translate_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def translate(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['translate_enabled'] == 'True':
            try:
                language_short = single_detection(args, api_key=self.config['keys']['detect_language_api_key'])
                language_long = pycountry.languages.get(alpha_2=language_short)
                try:
                    translated = GoogleTranslator(source=language_short, target='en').translate(args)
                except Exception as e:
                    print(e)
                    try:
                        translated = GoogleTranslator(source=language_long.name, target='en').translate(args)
                    except Exception as e:
                        print(e)
                        translated = GoogleTranslator(source='auto', target='en').translate(args)
                try:
                    response = 'From ' + language_long.name + ': ' + translated
                except Exception as e:
                    print(e)
                    response = 'From ' + language_short + ': ' + translated
                await ctx.send(response[:500])
            except Exception as e:
                await ctx.send(str(e.args[0]))

    @commands.cooldown(rate=1, per=float(config['options']['weather_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def weather(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['weather_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide a location')
            else:
                owm = OWM(self.config['keys']['owm_api_key'])
                mgr = owm.weather_manager()
                g = geocoders.GoogleV3(api_key=self.config['keys']['google_api_key'], domain='maps.googleapis.com')
                place = g.geocode(args)
                if place is not None:
                    # F = 1.8(K - 273) + 32
                    # C = K – 273.15
                    one_call = mgr.one_call(lat=place.latitude, lon=place.longitude)
                    temp_f = int(one_call.current.temperature('fahrenheit').get('temp', None))
                    temp_c = int((one_call.current.temperature('celsius').get('temp', None)))
                    f_temp_f = int(one_call.forecast_daily[1].temperature('fahrenheit').get('max', None))
                    f_temp_c = int(one_call.forecast_daily[1].temperature('celsius').get('max', None))
                    await ctx.send('The temperature in ' + place.address + ' is ' + str(temp_f) + '°F (' + str(temp_c) +
                                   '°C) and ' + one_call.current.detailed_status
                                   + ', Tomorrow: ' + str(f_temp_f) + '°F (' + str(f_temp_c) + '°C) and ' +
                                   one_call.forecast_daily[1].detailed_status)
                else:
                    await ctx.send('Location ' + args + ' not found.')

    @commands.cooldown(rate=1, per=float(config['options']['reddit_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def reddit(self, ctx: commands.Context):
        self.config.read(r'keys.ini')
        if self.config['options']['reddit_enabled'] == 'True':
            joke = self.reddit_get()
            q = queue.Queue()
            x = threading.Thread(target=self.reddit_confirm, args=('Confirm?', joke, q))
            x.start()
            while x.is_alive():
                await asyncio.sleep(0)
            result = q.get()
            if result:
                await ctx.send(joke)

    @commands.command(name='commands')
    async def help(self, ctx: commands.Context):
        output = 'Enabled Commands Are: '
        self.config.read(r'keys.ini')

        if self.config['options']['wiki_enabled'] == 'True':
            output += '!wiki '
        if self.config['options']['followage_enabled'] == 'True':
            output += '!followage '
        if self.config['options']['uptime_enabled'] == 'True':
            output += '!uptime '
        if self.config['options']['ai_enabled'] == 'True':
            output += '!ai '
        if self.config['options']['imagine_enabled'] == 'True':
            output += '!imagine '
        if self.config['options']['dream_enabled'] == 'True':
            output += '!dream '
        if self.config['options']['define_enabled'] == 'True':
            output += '!define '
        if self.config['options']['etymology_enabled'] == 'True':
            output += '!etymology '
        if self.config['options']['translate_enabled'] == 'True':
            output += '!translate '
        if self.config['options']['weather_enabled'] == 'True':
            output += '!weather '
        if self.config['options']['reddit_enabled'] == 'True':
            output += '!reddit '
        if self.config['options']['time_enabled'] == 'True':
            output += '!time '
        if self.config['options']['exchange_enabled'] == 'True':
            output += '!exchange '
        if self.config['options']['fact_enabled'] == 'True':
            output += '!fact '
        if self.config['options']['key_enabled'] == 'True':
            output += '!key '
        if self.config['options']['math_enabled'] == 'True':
            output += '!math '
        if self.config['options']['pokemon_enabled'] == 'True':
            output += '!pokemon '
        if self.config['options']['imdb_enabled'] == 'True':
            output += '!imdb '
        if self.config['options']['celeb_enabled'] == 'True':
            output += '!celeb '
        if self.config['options']['pinball_enabled'] == 'True':
            output += '!pinball '
        if self.config['options']['trivia_enabled'] == 'True':
            output += '!trivia '
        if self.config['options']['leaderboard_enabled'] == 'True':
            output += '!leaderboard '
        if self.config['options']['strain_enabled'] == 'True':
            output += '!strain '
        if self.config['options']['nasa_enabled'] == 'True':
            output += '!nasa '
        if self.config['options']['apod_enabled'] == 'True':
            output += '!apod'

        await ctx.send(output)

    @commands.cooldown(rate=1, per=float(config['options']['time_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def time(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['time_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide a location')
            else:
                g = geocoders.GoogleV3(api_key=self.config['keys']['google_api_key'], domain='maps.googleapis.com')
                place = g.geocode(args)
                if place is not None:
                    lat = place.latitude
                    lng = place.longitude
                    tz = g.reverse_timezone((lat, lng))
                    tz_object = timezone(str(tz))
                    newtime = datetime.datetime.now(tz_object)
                    await ctx.send('The current time in ' + place.address + ' is ' + newtime.strftime('%#I:%M %p'))
                else:
                    await ctx.send('Place \"' + args + '\" not found')

    @commands.cooldown(rate=1, per=float(config['options']['exchange_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def exchange(self, ctx: commands.Context, cur_from='usd', cur_to='eur', amount='1'):
        self.config.read(r'keys.ini')
        if self.config['options']['exchange_enabled'] == 'True':
            url = 'https://api.exchangerate.host/convert?from=' + cur_from + '&to=' + cur_to + '&amount=' + amount
            data = requests.get(url).json()
            await ctx.send(amount + ' ' + cur_from + ' = ' + str(data['result']) + ' ' + cur_to)

    @commands.cooldown(rate=1, per=float(config['options']['fact_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def fact(self, ctx: commands.Context):
        self.config.read(r'keys.ini')
        if self.config['options']['fact_enabled'] == 'True':
            url = 'https://uselessfacts.jsph.pl/random.json?language=en'
            fact = requests.get(url).json()
            # print(json.dumps(fact, indent=4, sort_keys=True))
            await ctx.send(fact['text'])

    @commands.cooldown(rate=1, per=float(config['options']['math_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def math(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['math_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide an equation')
            else:
                url = 'http://api.mathjs.org/v4/?expr=' + urllib.parse.quote(args)
                output = requests.get(url)
                await ctx.send(output.text)

    @commands.cooldown(rate=1, per=float(config['options']['imdb_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def imdb(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['imdb_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide a Movie, Show, or Game')
            else:
                try:
                    movies = self.ia.search_movie(args)
                    movie = movies[0]
                    # print(movie)
                    movie_id = movie.movieID
                    # print(movie_id)
                    movie_info = self.ia.get_movie(movie_id)
                    # print(movie_info.get('plot')[0])
                    return_string = movie.get('title') + ' (' + str(movie_info.get('year')) + '): ' +\
                        movie_info.get('plot')[0]
                    await ctx.send(return_string[:500])
                except IndexError:
                    await ctx.send('Entry not found')

    @commands.cooldown(rate=1, per=float(config['options']['celeb_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def celeb(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['imdb_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide a Celebrity')
            else:
                try:
                    people = self.ia.search_person(args)
                    person = people[0]
                    person_id = person.personID
                    bio = self.ia.get_person(person_id)
                    return_string = person.get('name') + ' - ' +\
                        ' '.join(re.split(r'(?<=[.:;])\s', bio.get('mini biography')[0])[:3])
                    await ctx.send(return_string)
                except IndexError:
                    await ctx.send('Entry not found')

    @commands.cooldown(rate=1, per=float(config['options']['pokemon_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def pokemon(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['pokemon_enabled'] == 'True':
            with open('pokedex.json', encoding='utf8') as pokedex:
                data = json.load(pokedex)
            pokemon = ''
            if args is None:
                pokemon_id = random.randint(1, len(data))
                for item in data:
                    if item['id'] == pokemon_id:
                        pokemon = item['name']['english']

            else:
                pokemon = args

            url = 'https://bulbapedia.bulbagarden.net/w/api.php?&format=json&action=parse&page=' \
                  + pokemon + '_(Pokémon)'
            try:
                parse = requests.get(url).json()['parse']['text']['*']
                soup = BeautifulSoup(parse, 'html.parser')
                description = ''
                for p in soup.find_all('p'):
                    if p.get_text().strip().lower().startswith(pokemon.lower()):
                        description = p.get_text().strip()
                        break
                flavor_texts = ['']
                try:
                    url = 'https://pokeapi.co/api/v2/pokemon-species/' + pokemon.lower()
                    headers = {
                        'User-Agent': 'pyWiki'
                    }
                    entry = requests.get(url, headers=headers).json()

                    flavor_texts = []
                    for entries in entry['flavor_text_entries']:
                        if entries['language']['name'] == 'en':
                            flavor_texts.append(entries['flavor_text'])

                    random.shuffle(flavor_texts)

                except requests.exceptions.JSONDecodeError as e:
                    print(e)
                output = description + ' ' + flavor_texts[0]
                await ctx.send(output.replace('\r', ' ').replace('\n', ' ')[:500])
            except KeyError:
                await ctx.send('Pokemon ' + pokemon + ' not found')

    @commands.cooldown(rate=1, per=float(config['options']['pinball_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def pinball(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['pinball_enabled'] == 'True':
            url = 'https://pinballmap.com/api/v1/machines.json'
            machines = requests.get(url).json()
            # print(json.dumps(machines,indent=4,sort_keys=True))
            if args is not None:
                last_ratio = 0
                output = ''
                for machine in machines['machines']:
                    if machine['name'].lower() == args.lower():
                        output = machine['name'] + ': ' + machine['ipdb_link']
                        break
                    try:
                        # print(args.lower() + ', ' + machine['name'].lower() + ": " +
                        #       str(fuzz.partial_ratio(args, machine['name'])))
                        ratio = fuzz.partial_ratio(args.lower(), machine['name'].lower())
                    except Exception as e:
                        print(e)
                        ratio = 0
                    if ratio > last_ratio and machine['ipdb_link'] != '':
                        last_ratio = ratio
                        output = machine['name'] + ': ' + machine['ipdb_link']
                await ctx.send(output)
            else:
                for item in machines['machines']:
                    if item['ipdb_link'] is None:
                        machines['machines'].remove(item)
                machine = random.choice(machines['machines'])
                await ctx.send(machine['name'] + ': ' + machine['ipdb_link'])

    @commands.cooldown(rate=1, per=float(config['options']['strain_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def strain(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['strain_enabled'] == 'True':
            with open('strain_data.json', encoding='utf8') as strain_data:
                strains = json.load(strain_data)
            # print(json.dumps(machines,indent=4,sort_keys=True))
            if args is not None:
                last_ratio = 0
                output = ''
                for strain in strains:
                    if strain['name'].lower() == args.lower():
                        description = ' '.join(re.split(r'(?<=[.:;])\s', strain['description'])[:3])
                        output = strain['name'] + ': ' + description
                        break
                    try:
                        ratio = fuzz.ratio(args.lower(), strain['name'].lower())
                    except Exception as e:
                        print(e)
                        ratio = 0
                    if ratio > last_ratio:
                        last_ratio = ratio
                        description = ' '.join(re.split(r'(?<=[.:;])\s', strain['description'])[:3])
                        output = strain['name'] + ': ' + description
                await ctx.send(output[:500])
            else:
                strain = random.choice(strains)
                description = ' '.join(re.split(r'(?<=[.:;])\s', strain['description'])[:3])
                output = strain['name'] + ': ' + description
                await ctx.send(output[:500])

    @commands.cooldown(rate=1, per=float(config['options']['nasa_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def nasa(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['nasa_enabled'] == 'True':
            if args is None:
                await ctx.send('Please provide search term')
            else:
                try:
                    url = 'https://images-api.nasa.gov/search?q=' + args + '&media_type=image'
                    response = requests.get(url).json()
                    # print(json.dumps(response, indent=4, sort_keys=True))
                    entry = random.choice(response['collection']['items'])
                    image_url = entry['links'][0]['href']
                    title = entry['data'][0]['title']
                    await ctx.send(title + ' - ' + image_url)
                except IndexError as e:
                    await ctx.send('No images found')

    @commands.cooldown(1, float(config['options']['apod_cooldown']), commands.Bucket.member)
    @commands.command()
    async def apod(self, ctx):
        if self.config['options']['apod_enabled'] == 'True':
            # date = datetime.date.today().strftime('%Y-%m-%d')
            url = 'https://api.nasa.gov/planetary/apod?api_key=' + self.config['keys']['NASA_api_key']
            # + '&date=' + date
            response = requests.get(url).json()
            # print(json.dumps(response, indent=4, sort_keys=True))
            image_url = response['url']
            title = response['title']
            await ctx.send(title + ' - ' + image_url)

    @commands.cooldown(rate=1, per=float(config['options']['trivia_cooldown']), bucket=commands.Bucket.channel)
    @commands.command()
    async def trivia(self, ctx: commands.Context):
        self.config.read(r'keys.ini')
        if self.config['options']['trivia_enabled'] == 'True' and ctx.channel.name not in self.trivia_guesses:
            self.trivia_guesses.update({ctx.channel.name: {}})
            fast = False
            bot_chatter = ctx.channel.get_chatter(self.nick)
            if bot_chatter.is_mod or bot_chatter.is_vip:
                fast = True
            url = self.config['variables']['trivia_url']
            trivia_object = requests.get(url).json()
            # print(json.dumps(trivia_object, indent=4, sort_keys=True))
            answers = trivia_object['results'][0]['incorrect_answers']
            answers.append(trivia_object['results'][0]['correct_answer'])
            random.shuffle(answers)
            index = ['(A)', '(B)', '(C)', '(D)']
            index2 = ['a', 'b', 'c', 'd']
            number = 0
            correct_answer = ''
            await ctx.send(unescape(trivia_object['results'][0]['question']))
            if not fast:
                await asyncio.sleep(2)
            for answer in answers:
                if answer == trivia_object['results'][0]['correct_answer']:
                    correct_answer = index2[number]
                answer = index[number] + ' ' + answer
                await ctx.send(unescape(answer))
                number += 1
                if not fast:
                    await asyncio.sleep(2)
            await asyncio.sleep(30)
            await ctx.send('The correct answer was (' + correct_answer.upper() + ') ' +
                           unescape(trivia_object['results'][0]['correct_answer']))
            if not fast:
                await asyncio.sleep(2)
            winners = 'Winners: '
            with open('winners.json', encoding='utf8') as infile:
                winner_list = json.load(infile)
            for key in self.trivia_guesses[ctx.channel.name]:
                if self.trivia_guesses[ctx.channel.name][key] == correct_answer:
                    if ctx.channel.name not in winner_list:
                        winner_list.update({ctx.channel.name: {}})
                    if key in winner_list[ctx.channel.name]:
                        winner_list[ctx.channel.name].update({key: winner_list[ctx.channel.name][key] + 1})
                    else:
                        winner_list[ctx.channel.name].update({key: 1})
                    with open('winners.json', 'w') as outfile:
                        json.dump(winner_list, outfile)
                    winners += key + ' '
            if winners != 'Winners: ':
                await ctx.send(winners)
            else:
                await ctx.send('Nobody Won')
            self.trivia_guesses.pop(ctx.channel.name)

    @commands.command()
    async def leaderboard(self, ctx: commands.Context):
        self.config.read(r'keys.ini')
        if self.config['options']['leaderboard_enabled'] == 'True':
            with open('winners.json', encoding='utf8') as infile:
                winner_list = json.load(infile)
            if ctx.channel.name in winner_list:
                winner_list = sorted(winner_list[ctx.channel.name].items(), key=lambda item: item[1])
                winner_list.reverse()
                winner_list = dict(winner_list)
                keys = list(winner_list)
                top5 = 1
                output = ''
                for key in keys:
                    output += '#' + str(top5) + ' - ' + key + ': ' + str(winner_list[key]) + ' '
                    top5 += 1
                    if top5 == 5:
                        break
                await ctx.send(output)
            else:
                await ctx.send('No Leaderboard Yet')

    @commands.cooldown(rate=1, per=float(config['options']['song_cooldown']), bucket=commands.Bucket.member)
    @commands.command()
    async def song(self, ctx: commands.Context, *, args=None):
        self.config.read(r'keys.ini')
        if self.config['options']['song_enabled'] == 'True':
            if args is None:
                await ctx.send('Please enter a song')
            else:
                song = self.genius.search_song(title=args)
                await ctx.send(song.title + ' - ' + song.artist + ': ' + song.url)

    @commands.cooldown(rate=1, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def death(self, ctx: commands.Context):
        if ctx.author.is_mod or ctx.author.is_broadcaster:
            deaths = random.randint(1, 1000000)
            broadcaster = await self.fetch_users([ctx.channel.name])
            await ctx.send(broadcaster[0].display_name + ' has died ' + str(deaths) +
                           ' time/s or something, we\'re not really counting.')

    @commands.cooldown(rate=1, per=10, bucket=commands.Bucket.member)
    @commands.command()
    async def snork(self, ctx: commands.Context):
        snoot = random.choice(list(ctx.channel.chatters))
        snoot = await self.fetch_users([snoot.name])
        await ctx.send(ctx.message.author.display_name + ' snorked ' + snoot[0].display_name)

    @commands.command()
    async def clear(self, ctx: commands.Context):
        self.config.read(r'keys.ini')
        if ctx.author.is_mod or ctx.author.is_broadcaster:
            self.config['variables']['chatters'] = '[]'
            with open('keys.ini', 'w') as configfile:
                self.config.write(configfile)

    @staticmethod
    def reddit_confirm(title, message, q):
        option = ctypes.windll.user32.MessageBoxW(None, message, title, 0x01 | 0x30 | 0x00001000)
        if option == 1:
            option = True
        else:
            option = False
        q.put(option)

    @staticmethod
    def ai_complete(self, message):
        self.config.read(r'keys.ini')
        moderate_input = openai.Moderation.create(input=message, model='text-moderation-latest')
        # print(json.dumps(moderate_input, indent=4, sort_keys=True))
        print('Input Flagged: ' + str(moderate_input.results[0]['flagged']))
        if not moderate_input.results[0]['flagged']:
            completion = openai.Completion.create(temperature=float(self.config['options']['temperature']),
                                                  max_tokens=int(self.config['options']['tokens']),
                                                  engine=self.config['options']['ai_engine'],
                                                  prompt=message)
            # print(json.dumps(completion, indent=4, sort_keys=True))
            print('Response: ' + completion.choices[0].text.strip())
            moderation = openai.Moderation.create(input=completion.choices[0].text, model='text-moderation-latest')
            # print(json.dumps(moderation, indent=4, sort_keys=True))
            print('Output Flagged: ' + str(moderation.results[0]['flagged']))
            if not moderation.results[0]['flagged']:
                return completion
            else:
                return 'Response Flagged'
        else:
            return 'Prompt Flagged'

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
                    re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\), ]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                               output)):
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

    def reddit_get(self):
        random.seed()

        headlines = []

        config = configparser.ConfigParser()
        config.read(r'keys.ini')

        urls = json.loads(config.get('variables', 'reddit_urls'))

        random.shuffle(urls)

        headlines.append(self.getjoke(urls[0]))

        random.shuffle(headlines)
        return headlines[0]


def cleanup():
    print('Exiting')
    sys.exit()


atexit.register(cleanup)
bot = Bot()
bot.run()
