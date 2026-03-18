#!/usr/bin/python3
import random
import discord
from discord.utils import get
import yt_dlp as youtube_dl
import asyncio
import numpy as np
import subprocess
import public_ip as ip
from ollama import Client



#youtube_dl library configs
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}
ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


#globale Variablen
msg = ""
messageQueue = None
nameQueue = []
linkQueue = []
thumbnailQueue = []
urlQueue = []
nightcoreQueue = []
messageId = ""
channel_id = ""
skipFlip = 0
isSkipped = False
isSongLooped = False
isPlaylistLooped = False
isRickRolled = False
isNightcore = False
isNotPlaying = True

class Queue(discord.VoiceClient):
    def __init__(self,voice_client):
        self.voice_client = voice_client

    @classmethod
    async def updateList(self, message):
        global nameQueue
        global messageQueue
        global msg

        for i, k in enumerate(nameQueue):
            if i > 10:
                msg += "more..."
                break
            else:
                msg += str(i + 1) + ". " + str(k) + "\n"
        messageQueue = await message.channel.send(msg)
        msg = ""
        numElems = np.array(nameQueue)
        while len(nameQueue) != 0:
            await asyncio.sleep(1)
            if not np.array_equal(numElems,np.array(nameQueue)) and len(nameQueue) != 0:
                await messageQueue.delete()
                for i, k in enumerate(nameQueue):
                    if i > 10:
                        msg += "more..."
                        break
                    else:
                        msg += str(i + 1) + ". " + str(k) + "\n"
                messageQueue = await message.channel.send(msg)
                msg = ""
                numElems = np.array(nameQueue)
            elif len(nameQueue) == 0:
                await messageQueue.delete()

    @classmethod
    async def updatePic(self):
        global nameQueue
        global thumbnailQueue
        global urlQueue
        global channel_id

        newEmbed = discord.Embed(
            title=nameQueue[0],
            colour=discord.Colour.dark_orange()
        )
        newEmbed.set_image(url=thumbnailQueue[0])
        newEmbed.set_footer(text=urlQueue[0])
        message_embed = await client.get_channel(int(channel_id)).fetch_message(int(messageId))
        await message_embed.edit(embed=newEmbed)

        numElems = np.array(nameQueue)
        while len(nameQueue) != 0:
            await asyncio.sleep(1)
            if not np.array_equal(numElems,np.array(nameQueue)) and len(nameQueue) != 0:
                newEmbed = discord.Embed(
                    title=nameQueue[0],
                    colour=discord.Colour.dark_orange()
                )
                newEmbed.set_image(url=thumbnailQueue[0])
                newEmbed.set_footer(text=urlQueue[0])
                message_embed = await client.get_channel(int(channel_id)).fetch_message(int(messageId))
                await message_embed.edit(embed=newEmbed)
                numElems = np.array(nameQueue)
            elif len(nameQueue) == 0:
                newEmbed = discord.Embed(
                    title="No song playing currently",
                    colour=discord.Colour.dark_orange()
                )
                newEmbed.set_image(url="") #PLACEHOLDER FOR A PICTURE
                message_embed = await client.get_channel(int(channel_id)).fetch_message(int(messageId))
                await message_embed.edit(embed=newEmbed)

    async def control(self, voice_client, message):
        global channel_id
        global nameQueue
        global linkQueue
        global thumbnailQueue
        global messageId
        global urlQueue
        global isSkipped
        global isSongLooped
        global isPlaylistLooped
        global isNotPlaying
        try:
            player = await YTDLSource.getPlayer(urlQueue[0], linkQueue[0])
        except:
            isNotPlaying = True
            while isNotPlaying:
                await asyncio.sleep(1)
                try:
                    player = await YTDLSource.getPlayer(urlQueue[0], linkQueue[0])
                    isNotPlaying = False
                except:
                    print("ist nicht")

        voice_client.play(player)
        a = nameQueue[0]
        b = thumbnailQueue[0]
        c = linkQueue[0]
        d = urlQueue[0]

        asyncio.create_task(Queue.updateList(message))
        asyncio.create_task(Queue.updatePic())

        while len(nameQueue) != 0:
            await asyncio.sleep(1)
            if voice_client.is_paused():
                pass
            elif isSkipped or not voice_client.is_playing():
                if isSkipped:
                    voice_client.stop()
                    isSkipped = False
                if isSongLooped:
                    player = await YTDLSource.getPlayer(urlQueue[0], linkQueue[0])
                    voice_client.play(player)
                elif isPlaylistLooped:
                    tempNameA = a
                    tempNameB = b
                    tempNameC = c
                    tempNameD = d

                    nameQueue.remove(a)
                    thumbnailQueue.remove(b)
                    linkQueue.remove(c)
                    urlQueue.remove(d)

                    nameQueue.append(tempNameA)
                    thumbnailQueue.append(tempNameB)
                    linkQueue.append(tempNameC)
                    urlQueue.append(tempNameD)

                    player = await YTDLSource.getPlayer(urlQueue[0], linkQueue[0])
                    voice_client.play(player)

                    a = nameQueue[0]
                    b = thumbnailQueue[0]
                    c = linkQueue[0]
                    d = urlQueue[0]
                else:
                    nameQueue.remove(a)
                    thumbnailQueue.remove(b)
                    linkQueue.remove(c)
                    urlQueue.remove(d)

                    player = await YTDLSource.getPlayer(urlQueue[0], linkQueue[0])
                    voice_client.play(player)

                    a = nameQueue[0]
                    b = thumbnailQueue[0]
                    c = linkQueue[0]
                    d = urlQueue[0]
            elif voice_client.is_playing() and not voice_client.is_paused():
               pass


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1):
        super().__init__(source, volume)
        self.data = data

    @classmethod
    async def add_song_to_queue(cls, entries, author,isPlaylist=False,fromNightcore=False):
        global linkQueue
        global nameQueue
        global thumbnailQueue
        global urlQueue
        global isNotPlaying
        global nightcoreQueue
        global isNightcore
        if(isPlaylist):
            temp = []
            for i in entries:
                temp.append(i)
            for i in temp:
                data = i
                url = data['webpage_url']
                link = data['url']
                name = data['title']
                thumbnail = data['thumbnail']
                urlQueue.append(url)
                linkQueue.append(link)
                nameQueue.append(name + " @" + author)
                if isNightcore and fromNightcore is False:
                    nightcoreQueue.append(name + " @" + author)
                thumbnailQueue.append(thumbnail)
                #print(name + " with the url " + url + " and the thumbnail " + thumbnail)
        else:
            try:

                data = entries[0]

                url = data['webpage_url']
                link = data['url']
                name = data['title']
                thumbnail = data['thumbnail']
                urlQueue.append(url)
                linkQueue.append(link)
                nameQueue.append(name + " @" + author)
                if isNightcore and fromNightcore is False:
                    nightcoreQueue.append(name + " @" + author)
                thumbnailQueue.append(thumbnail)
            except:

                data = entries

                url = data['webpage_url']
                link = data['url']
                name = data['title']
                thumbnail = data['thumbnail']
                urlQueue.append(url)
                linkQueue.append(link)
                nameQueue.append(name + " @" + author)
                if isNightcore and fromNightcore is False:
                    nightcoreQueue.append(name + " @" + author)
                thumbnailQueue.append(thumbnail)

        #print("urlQueue -> " + str(urlQueue))
        #print("LinkQueue -> " + str(linkQueue))
        #print("nameQueue -> " + str(nameQueue))
        #print("thumbnailQueue -> " + str(thumbnailQueue))

    @classmethod
    async def getPlayer(cls, url, filename, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    @classmethod
    async def getUrlInfos(cls, url,author,message,fromNightcore=False, *, loop=None ):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        except youtube_dl.utils.DownloadError:
            embed = discord.Embed(
                description="Anscheinend ist der Bot nicht alt genug für dieses Lied :(",
                colour=discord.Colour.dark_orange()
            )
            potato = await message.channel.send(embed=embed)
            await asyncio.sleep(5)
            await client.delete_message(potato)

        if 'entries' in data:
            entries = list(data.get('entries'))
            if len(entries) > 1:
                await YTDLSource.add_song_to_queue(entries,author,True,fromNightcore=fromNightcore)
            else:
                await YTDLSource.add_song_to_queue(entries,author,fromNightcore=fromNightcore)
        elif 'formats' in data:
            await YTDLSource.add_song_to_queue(data,author,fromNightcore=fromNightcore)

    async def get_length(filename):
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
        print(result.stdout)
        return float(result.stdout)

    @classmethod
    async def getNightcore(cls,message,first=False):
        global nightcoreQueue
        names = []
        while isNotPlaying or np.array_equal(np.array([]),np.array(nightcoreQueue)) and first is False:
            await asyncio.sleep(1)
        #names = nameQueue.copy()
        for name in nightcoreQueue:
            names.append(name)
        nightcoreQueue = []
        for name in names:
            await YTDLSource.getUrlInfos(str(name).split('@')[0] + "nightcore", str(name).split('@')[1], message,fromNightcore=True)

class MyClient(discord.Client):

    #Einloggen
    async def on_ready(self):
        print("Moin ihr Kartoffeln :P Ich bin jetzt da, ihr braucht keine Angst mehr haben :3")

    #Nachricht geschrieben
    async def on_message(self,message):
        global messageId
        global channel_id
        global nameQueue
        global linkQueue
        global urlQueue
        global thumbnailQueue
        global isSongLooped
        global isSkipped
        global skipFlip
        global isPlaylistLooped

        if "NAME_OF_THE_BOT" in str(message.author):
            pass
        else:
            print(message.content + " from " + str(message.author))

        if message.author == client.user:
            return

        #Chat-Input-Befehle
        if message.content.startswith("pot"):
            message_str = str(message.content)
            #print(message)

            #Hilfe-Befehl
            if "help" in message_str:
                embed = discord.Embed(
                    title="Hier sind ein paar helfende Befehle: ",
                    colour=discord.Colour.dark_orange()
                )
                embed.add_field(name="Utility", value="pot chat [nachricht] - sprich mit mir "
                                                                       " :P\npot w2g - der Link zu einem "
                                                                       " Watch2Gether-Room", inline=True)
                embed.add_field(name="Einstellungen", value="pot setup - lass die Kraft des Bots frei", inline=True)
                embed.add_field(name="Musik-Befehle", value="pot play [url] - Lass den Bot bei dir spawnen und "
                                                            "deine Ohren mit wundervollen Klängen beschallen \npot "
                                                            "stop - Halte den Bot auf, bevor sie dich in ihren "
                                                            "Ban reißt \npot pause - Bitte den Bot kurz zu "
                                                            "warten \npot resume - Lass den Bot fortfahren\npot "
                                                            "move [titelnummer] [titelnummer] - Wechsel deine Titel "
                                                            "untereinander\npot loop - Der Bot beschallt deine "
                                                            "Ohren Non-Stop mit deinem Lieblingslied\npot skip - Der "
                                                            "Bot beschützt dich vor schlechten Songs\npot "
                                                            "remove [titelnummer] - wenn du den Bot nett fragst, "
                                                            "dann entfernt sie bestimmt das doofe Lied\npot counter - "
                                                            "Gibt dir die List der aktuellen Songs aus\npot get_song ["
                                                            "titelnummer] - Gibt dir den Song der Titelnummer aus\n"
                                                            "pot get_ip - gibt dir die IP-Adresse für alle lokale Server ", inline=False) #just examples for a help message
                potato = await message.channel.send(embed=embed)
                await client.delete_message(message)
                await asyncio.sleep(10)
                await client.delete_message(potato)

            #Chat-Befehl
            elif "chat" in message_str:
                try:
                    clientChat = Client(
                        host='http://192.168.178.33:11434'
                    )
                    response = clientChat.chat(model='deepseek-potato', messages=[
                        {
                            "role": "user",
                            "content": message_str.split("chat ")[1],
                        }
                    ])
                    potato = await message.channel.send(response.message.content)
                    await client.delete_message(message)
                    await asyncio.sleep(15)
                    await client.delete_message(potato)
                except Exception as e:
                    print(e)
                    short_author = str(message.author).split("#")
                    potato = await message.channel.send('Hey ' + str(short_author[0]) + ', wie gehts du alte Kartoffel?')
                    potato2 = await message.channel.send('Lass uns später reden, ich bin etwas müde :)')
                    await client.delete_message(message)
                    await asyncio.sleep(4)
                    await client.delete_message(potato)
                    await client.delete_message(potato2)

            #Setup-Befehl
            elif "setup" in message_str:
                emojis = ["⏯", "⏹", "⏩", "🔁", "🔀", "👮", "😞","🎅"]
                guild = message.guild
                file = open("/root/bot/guild.txt", 'w') #PATH TO THE BOT
                file.write(str(message.guild.id))
                file.close()
                channels = await guild.create_text_channel('songrequest')
                channel_id = channels.id
                channel_send = client.get_channel(channel_id)
                embed = discord.Embed(
                    title="No song playing currently",
                    colour=discord.Colour.dark_orange()
                )
                embed.set_image(url="") #placeholder for a picture
                messages = await channel_send.send(embed=embed)
                message_id = messages.id
                file = open("/root/bot/message_id.txt", 'w') #PATH TO THE BOT
                file.write(str(message_id))
                file.close()
                file = open("/root/bot/channel_id.txt", 'w') #PATH TO THE BOT
                file.write(str(channel_id))
                file.close()
                messageId = message_id
                for i in emojis:
                    await messages.add_reaction(i)

                await client.delete_message(message)

            #Join-Befehl
            elif "join" in message_str:
                # where = message_str.split(" ")[2]
                where = message.author.voice.channel
                print(where)
                #channel = get(message.guild.channels, name=where)
                voicechannel = await where.connect()

                await client.delete_message(message)

            #Play-Befehl
            elif "play" in message_str:
                url = message_str[2]
                voice_client = await client.join(message)
                await YTDLSource.getUrlInfos(url)
                await client.delete_message(message)
                if voice_client.is_playing:
                    try:
                        await Queue.control(self, voice_client, message)
                    except:
                        pass
                else:
                    await Queue.control(self, voice_client, message)

            #Stop-Befehl
            elif "stop" in message_str:
                server = message.guild
                voice_client2 = server.voice_client
                voice_client2.stop()
                linkQueue = []
                urlQueue = []
                nameQueue = []
                thumbnailQueue = []

                await client.delete_message(message)

            #Resume-Befehl
            elif "resume" in message_str:
                server = message.guild
                voice_client2 = server.voice_client
                voice_client2.resume()

                await client.delete_message(message)

            #Pause-Befehl
            elif "pause" in message_str:
                server = message.guild
                voice_client2 = server.voice_client
                voice_client2.pause()

                await client.delete_message(message)

            elif "remove" in message_str:
                await client.delete_message(message)
                arr = message_str.split()
                if len(arr) < 3:
                    embed = discord.Embed(
                        description="Da fehlt doch etwas oder?\nProbier doch mal pot help aus :)",
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)
                else:
                    if len(nameQueue) == 0:
                        embed = discord.Embed(
                            description="Irgendwie läuft gerade nichts...\nProbier doch mal pot help aus :)",
                            colour=discord.Colour.dark_orange()
                        )
                        potato = await message.channel.send(embed=embed)
                        await asyncio.sleep(3)
                        await client.delete_message(potato)
                    else:
                        if len(nameQueue) >= int(arr[2])-1 and int(arr[2])-1 != 0:
                            i = int(arr[2])-1
                            rem_a = nameQueue[i]
                            rem_b = linkQueue[i]
                            rem_c = urlQueue[i]
                            rem_d = thumbnailQueue[i]

                            nameQueue.remove(rem_a)
                            linkQueue.remove(rem_b)
                            urlQueue.remove(rem_c)
                            thumbnailQueue.remove(rem_d)
                        else:
                            embed = discord.Embed(
                                description="Die Titel existieren nicht :/\nProbier doch mal pot help aus :)",
                                colour=discord.Colour.dark_orange()
                            )
                            potato = await message.channel.send(embed=embed)
                            await asyncio.sleep(3)
                            await client.delete_message(potato)

            elif "move" in message_str:

                await client.delete_message(message)
                arr = message_str.split()
                if len(arr) < 4:
                    embed = discord.Embed(
                        description="Da fehlt doch etwas oder?\nProbier doch mal pot help aus :)",
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)
                else:
                    if len(nameQueue) == 0:
                        embed = discord.Embed(
                            description="Irgendwie läuft gerade nichts...\nProbier doch mal pot help aus :)",
                            colour=discord.Colour.dark_orange()
                        )
                        potato = await message.channel.send(embed=embed)
                        await asyncio.sleep(3)
                        await client.delete_message(potato)
                    else:
                        if len(nameQueue) >= int(arr[2])-1 and len(nameQueue) >= int(arr[3])-1 and int(arr[2])-1 != 0 and int(arr[3])-1 != 0:
                            temp_a = linkQueue[int(arr[2])-1]
                            temp_b = nameQueue[int(arr[2])-1]
                            temp_c = urlQueue[int(arr[2])-1]
                            temp_d = thumbnailQueue[int(arr[2])-1]

                            linkQueue[int(arr[2])-1] = linkQueue[int(arr[3])-1]
                            nameQueue[int(arr[2])-1] = nameQueue[int(arr[3])-1]
                            urlQueue[int(arr[2])-1] = urlQueue[int(arr[3])-1]
                            thumbnailQueue[int(arr[2])-1] = thumbnailQueue[int(arr[3])-1]

                            linkQueue[int(arr[3])-1] = temp_a
                            nameQueue[int(arr[3])-1] = temp_b
                            urlQueue[int(arr[3])-1] = temp_c
                            thumbnailQueue[int(arr[3])-1] = temp_d
                        else:

                            embed = discord.Embed(
                                description="Die Titel existieren nicht :/\nProbier doch mal pot help aus :)",
                                colour=discord.Colour.dark_orange()
                            )
                            potato = await message.channel.send(embed=embed)
                            await asyncio.sleep(3)
                            await client.delete_message(potato)

            elif "loop" in message_str:
                await client.delete_message(message)
                if len(nameQueue) == 0:
                    embed = discord.Embed(
                        description="Irgendwie läuft gerade nichts...\nProbier doch mal pot help aus :)",
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)
                else:
                    skipFlip += 1

                    if skipFlip == 1:
                        isSongLooped = True
                        embed = discord.Embed(
                            description="current song is looped...",
                            colour=discord.Colour.dark_orange()
                        )
                        looped = await message.channel.send(embed=embed)
                        await asyncio.sleep(1)
                        await looped.delete()
                    elif skipFlip == 2:
                        isSongLooped = False
                        isPlaylistLooped = True
                        embed = discord.Embed(
                            description="current playlist is looped...",
                            colour=discord.Colour.dark_orange()
                        )
                        looped = await message.channel.send(embed=embed)
                        await asyncio.sleep(1)
                        await looped.delete()
                    elif skipFlip == 3:
                        isPlaylistLooped = False
                        skipFlip = 0
                        embed = discord.Embed(
                            description="current song is not looped anymore...",
                            colour=discord.Colour.dark_orange()
                        )
                        looped = await message.channel.send(embed=embed)
                        await asyncio.sleep(1)
                        await looped.delete()

            elif "skip" in message_str:
                await client.delete_message(message)
                if len(nameQueue) == 0:
                    embed = discord.Embed(
                        description="Irgendwie läuft gerade nichts...\nProbier doch mal pot help aus :)",
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)
                else:
                    isSkipped = True

            elif "counter" in message_str:
                await client.delete_message(message)
                if len(nameQueue) != 0:
                    embed = discord.Embed(
                        description="Die Größe der Song-Liste beträgt: " + str(len(nameQueue)),
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)
                else:
                    embed = discord.Embed(
                        description="Irgendwie läuft gerade nichts...\nProbier doch mal pot help aus :)",
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)

            elif "get_song" in message_str:
                await client.delete_message(message)
                arr = message_str.split()
                if len(nameQueue) == 0:
                    embed = discord.Embed(
                        description="Irgendwie läuft gerade nichts...\nProbier doch mal pot help aus :)",
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)
                else:
                    if len(arr) < 3:
                        embed = discord.Embed(
                            description="Da fehlt doch etwas oder?\nProbier doch mal pot help aus :)",
                            colour=discord.Colour.dark_orange()
                        )
                        potato = await message.channel.send(embed=embed)
                        await asyncio.sleep(3)
                        await client.delete_message(potato)
                    else:
                        embed = discord.Embed(
                            description="Dieser kartoffelige Song heißt " + str(nameQueue[int(arr[2])-1]),
                            colour=discord.Colour.dark_orange()
                        )
                        potato = await message.channel.send(embed=embed)
                        await asyncio.sleep(3)
                        await client.delete_message(potato)

            elif "w2g" in message_str:
                await client.delete_message(message)
                embed = discord.Embed(
                    description="", # LINK TO A WATCH 2 GETHER ROOM
                    colour=discord.Colour.dark_orange()
                )
                potato = await message.channel.send(embed=embed)
                await asyncio.sleep(5)
                await client.delete_message(potato)
                
            elif "get_ip" in message_str:
                await client.delete_message(message)
                ipPublic = ip.get()
                embed = discord.Embed(
                    description=ipPublic,
                    colour=discord.Colour.dark_orange()
                )
                potato = await message.channel.send(embed=embed)
                await asyncio.sleep(5)
                await client.delete_message(potato)

            #Error-Befehl
            elif " " in message_str:
                embed = discord.Embed(
                    description="Probiere doch mal pot help aus ;)",
                    colour=discord.Colour.dark_orange()
                )
                potato = await message.channel.send(embed=embed)

                await client.delete_message(message)
                await asyncio.sleep(2)
                await client.delete_message(potato)

        #Voice-Client-Steuerung
        if message.channel is discord.utils.get(message.guild.channels, name="songrequest") and "pot playlist" not in message.content:
            if "pot " in message.content or str(message.author) == "NAME_OF_THE_BOT":
                pass
            else:
                if isRickRolled:
                    #1.April
                    if "Never gonna give" in message.content:
                        print(message.content)
                    else:
                        message.content = "you just got rick rolled lol"

                print(message.content + " from " + str(message.author))
                url = str(message.content)
                author = str(message.author).split("#")[0]
                voice_client = await client.join(message)
                asyncio.get_event_loop().create_task(YTDLSource.getUrlInfos(url,author,message))
                if isNightcore:
                    asyncio.get_event_loop().create_task(YTDLSource.getNightcore(message))
                    await client.delete_message(message)
                else:
                    await client.delete_message(message)
                if voice_client.is_playing:
                    try:
                        await Queue.control(self, voice_client, message)
                    except:
                        pass
                else:
                    await Queue.control(self, voice_client, message)





    async def delete_message(self, message):
        await asyncio.sleep(1)
        await message.delete()

    async def join(self,message):
        try:
            where = message.author.voice.channel
            voicechannel = await where.connect()
        except:
            pass
        server = message.guild
        voice_client = server.voice_client

        return voice_client


    #Reaction-Befehle
    async def on_raw_reaction_add(self, payload):
        global messageId
        global messageQueue
        global linkQueue
        global nameQueue
        global urlQueue
        global thumbnailQueue
        global isSkipped
        global isSongLooped
        global isPlaylistLooped
        global channel_id
        global skipFlip
        global isRickRolled
        global isNightcore

        #print(str(payload))
        print(payload.emoji.name + " from " + payload.member.name)
        channel = client.get_channel(payload.channel_id)
        server = client.get_guild(payload.guild_id)
        message = await channel.fetch_message(payload.message_id)
        reaction = get(message.reactions, emoji=payload.emoji.name)
        user = client.get_user(payload.user_id)
        emojis = ["⏯", "⏹", "⏩", "🔁", "🔀", "👮", "😞","🎅"]
        #print(message)
        voice_client2 = server.voice_client

        if "potatoetyl" == payload.member.name or str(payload.channel_id) != channel_id:
            pass
        else:
            #Play/Resume-Befehle
            if str(reaction) == "⏯" and voice_client2.is_playing():
                voice_client2.pause()
            elif str(reaction) == "⏯" and voice_client2.is_paused():
                voice_client2.resume()

            #Stop-Befehle
            elif str(reaction) == "⏹":
                voice_client2.stop()
                linkQueue = []
                urlQueue = []
                nameQueue = []
                thumbnailQueue = []

            elif str(reaction) == "🔀":
                if len(nameQueue) == 2:
                    pass
                else:
                    temp_a = nameQueue
                    temp_b = linkQueue
                    temp_c = urlQueue
                    temp_d = thumbnailQueue

                    for i in range(1,len(nameQueue)):
                        ran = random.randint(1,len(nameQueue)-1)
                        ran2 = random.randint(1,len(nameQueue)-1)
                        tem_a = temp_a[ran]
                        tem_b = temp_b[ran]
                        tem_c = temp_c[ran]
                        tem_d = temp_d[ran]

                        temp_a[ran] = temp_a[ran2]
                        temp_b[ran] = temp_b[ran2]
                        temp_c[ran] = temp_c[ran2]
                        temp_d[ran] = temp_d[ran2]

                        temp_a[ran2] = tem_a
                        temp_b[ran2] = tem_b
                        temp_c[ran2] = tem_c
                        temp_d[ran2] = tem_d

                    nameQueue = temp_a
                    linkQueue = temp_b
                    urlQueue = temp_c
                    thumbnailQueue = temp_d


            elif str(reaction) == "⏩":
                if voice_client2.is_playing():
                    isSkipped = True

            elif str(reaction) == "🔁":
                if len(nameQueue) == 0:
                    embed = discord.Embed(
                        description="Irgendwie läuft gerade nichts...\nProbier doch mal pot help aus :)",
                        colour=discord.Colour.dark_orange()
                    )
                    potato = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await client.delete_message(potato)
                else:
                    skipFlip += 1

                    if skipFlip == 1:
                        isSongLooped = True
                        embed = discord.Embed(
                            description="current song is looped...",
                            colour=discord.Colour.dark_orange()
                        )
                        looped = await message.channel.send(embed=embed)
                        await asyncio.sleep(1)
                        await looped.delete()
                    elif skipFlip == 2:
                        isSongLooped = False
                        isPlaylistLooped = True
                        embed = discord.Embed(
                            description="current playlist is looped...",
                            colour=discord.Colour.dark_orange()
                        )
                        looped = await message.channel.send(embed=embed)
                        await asyncio.sleep(1)
                        await looped.delete()
                    elif skipFlip == 3:
                        isPlaylistLooped = False
                        skipFlip = 0
                        embed = discord.Embed(
                            description="current song is not looped anymore...",
                            colour=discord.Colour.dark_orange()
                        )
                        looped = await message.channel.send(embed=embed)
                        await asyncio.sleep(1)
                        await looped.delete()


            #Alaaaaarm
            elif str(reaction) == "👮":
                if isRickRolled is False:
                    isRickRolled = True
                else:
                    isRickRolled = False

            #Kai hat frei - Befehl
            elif str(reaction) == "😞":
                if isNightcore is False:
                    isNightcore = True
                    embed = discord.Embed(
                        description="Nightcore Mode enabled...",
                        colour=discord.Colour.dark_orange()
                    )
                    looped = await message.channel.send(embed=embed)
                    await asyncio.sleep(1)
                    await looped.delete()
                    try:
                        asyncio.get_event_loop().create_task(YTDLSource.getNightcore(message,first=True))
                    except:
                        print()
                else:
                    embed = discord.Embed(
                        description="Nightcore Mode disabled...",
                        colour=discord.Colour.dark_orange()
                    )
                    looped = await message.channel.send(embed=embed)
                    await asyncio.sleep(1)
                    await looped.delete()
                    isNightcore = False

            #Weihnachten
            elif str(reaction) == "🎅":
                print("nichts")

            if reaction.count > 1:
                await message.remove_reaction(reaction, client.get_user(payload.user_id))

#init
try:
	with open("/root/bot/message_id.txt") as f: #PATH TO THE BOT
		m = f.read()
		if m != "":
			messageId = m
except:
	print("Problem 1")

try:
    with open("/root/bot/channel_id.txt") as f: #PATH TO THE BOT
        m = f.read()
        if m != "":
            channel_id = m
except:
    print("Problem 2")



Intents = discord.Intents().all()
client = MyClient(intents=Intents)
client.run("") # API KEY FOR THE BOT
