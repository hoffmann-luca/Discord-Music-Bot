#!/usr/bin/python3
import random
import discord
from discord.utils import get
import yt_dlp as youtube_dl
import asyncio
import numpy as np
import subprocess
from ollama import Client
import json
import sys
import os
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen

# yt-dlp configuration
single_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

playlist_options = {
    'extract_flat': 'in_playlist',
    'lazy_playlist': True,
    'noplaylist': False,

    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'source_address': '0.0.0.0'
}


ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ytdl_single = youtube_dl.YoutubeDL(single_options)
ytdl_playlist = youtube_dl.YoutubeDL(playlist_options)
ytdlp_request_queue = asyncio.Queue()

#globale Variablen
POTATO_IMAGE_URL = "https://raw.githubusercontent.com/hoffmann-luca/Discord-Music-Bot/refs/heads/main/assets/pota2.png"
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

def get_public_ipv4():
    try:
        with urlopen(
            "https://api4.ipify.org",
            timeout=5
        ) as response:
            return response.read().decode("utf-8").strip()
    except Exception as e:
        print(
            "[PUBLIC IP ERROR]",
            type(e).__name__,
            str(e)
        )
        return "IP konnte nicht ermittelt werden"

def get_playlist_id(url):
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        return params.get("list", [None])[0]

    except Exception:
        return None


def is_url(value):
    try:
        result = urlparse(value)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False
def is_real_youtube_playlist(url):
    playlist_id = get_playlist_id(url)

    # Keine Playlist-ID
    if not playlist_id:
        return False

    # YouTube Mix / Radio ignorieren
    if playlist_id.startswith("RD"):
        return False

    # alles andere mit list= behandeln wir als Playlist
    return True
async def extract_single_isolated(url):
    args = [
        "nice", "-n", "15",
        sys.executable,
        "-m", "yt_dlp",

        "--dump-single-json",
        "--quiet",
        "--no-warnings",
        "--no-playlist",
        "--default-search", "auto",

        url
    ]

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            stderr.decode(errors="replace")
        )

    return json.loads(stdout)

async def extract_playlist_isolated(
    url,
    author,
    fromNightcore=False
):
    playlist_id = get_playlist_id(url)

    if not playlist_id:
        return

    playlist_url = (
        "https://www.youtube.com/playlist"
        f"?list={playlist_id}"
    )

    args = [
        "nice", "-n", "15",
        sys.executable,
        "-m", "yt_dlp",

        "--flat-playlist",
        "--lazy-playlist",
        "--dump-json",
        "--quiet",
        "--no-warnings",

        playlist_url
    ]

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stderr_task = asyncio.create_task(
        process.stderr.read()
    )

    count = 0

    async for raw_line in process.stdout:

        try:
            entry = json.loads(raw_line)

            await YTDLSource.add_playlist_entry(
                entry,
                author,
                fromNightcore
            )

            count += 1

            print(
                f"[PLAYLIST] #{count}: "
                f"{entry.get('title')}"
            )

        except Exception as e:
            print(
                "[PLAYLIST ENTRY ERROR]",
                type(e).__name__,
                str(e)
            )

        # Discord-Eventloop freigeben
        await asyncio.sleep(0)

    await process.wait()

    stderr = await stderr_task

    if process.returncode != 0:
        print(
            "[PLAYLIST YTDLP ERROR]",
            stderr.decode(errors="replace")
        )

    print(
        f"[PLAYLIST] Fertig: {count} Titel"
    )

async def search_youtube_isolated(query):
    args = [
        "taskset", "-c", "1",
        "nice", "-n", "15",
        sys.executable,
        "-m", "yt_dlp",

        "--flat-playlist",
        "--dump-json",
        "--quiet",
        "--no-warnings",

        f"ytsearch1:{query}"
    ]

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            stderr.decode(errors="replace")
        )

    lines = [
        line
        for line in stdout.decode().splitlines()
        if line.strip()
    ]

    if not lines:
        raise RuntimeError(
            f"Keine Suchergebnisse für: {query}"
        )

    data = json.loads(lines[0])

    video_id = data.get("id")

    if not video_id:
        raise RuntimeError(
            "Suchergebnis enthält keine Video-ID"
        )

    # Wichtig:
    # Aus dem flachen Suchergebnis eine normale
    # YouTube-URL für unsere Queue machen.
    data["webpage_url"] = (
        f"https://www.youtube.com/watch?v={video_id}"
    )

    return data

async def ytdlp_worker():

    while True:

        job = await ytdlp_request_queue.get()

        try:

            if job["is_playlist"]:

                await extract_playlist_isolated(
                    job["url"],
                    job["author"],
                    job["fromNightcore"]
                )

            else:

                input_value = job["url"]

                if is_url(input_value):

                    print("[YTDLP] Direkte URL")

                    data = await extract_single_isolated(
                        input_value
                    )

                else:

                    print(
                        f"[YTDLP SEARCH] Suche: {input_value}"
                    )

                    data = await search_youtube_isolated(
                        input_value
                    )

                await YTDLSource.add_song_to_queue(
                    data,
                    job["author"],
                    False,
                    fromNightcore=job["fromNightcore"]
                )

                print(
                    "[QUEUE] Hinzugefügt:",
                    data.get("title")
                )

        except Exception as e:

            print(
                "[YTDLP WORKER ERROR]",
                type(e).__name__,
                str(e)
            )

        finally:
            ytdlp_request_queue.task_done()

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
                newEmbed.set_image(url=POTATO_IMAGE_URL)
                message_embed = await client.get_channel(int(channel_id)).fetch_message(int(messageId))
                await message_embed.edit(embed=newEmbed)

    async def control(self, voice_client, message):
        global nameQueue
        global linkQueue
        global thumbnailQueue
        global urlQueue
        global isSkipped
        global isSongLooped
        global isPlaylistLooped
        global isNotPlaying

        async def create_player():
            global isNotPlaying

            while urlQueue:
                try:
                    player = await YTDLSource.getPlayer(urlQueue[0], linkQueue[0])
                    isNotPlaying = False
                    return player
                except Exception as e:
                    isNotPlaying = True
                    print("GET PLAYER ERROR:")
                    print(type(e).__name__, str(e))
                    await asyncio.sleep(1)

            return None

        if not urlQueue:
            return

        # control() darf nicht parallel einen zweiten Player starten.
        if voice_client.is_playing() or voice_client.is_paused():
            return

        player = await create_player()
        if player is None:
            return

        voice_client.play(player)

        asyncio.create_task(Queue.updateList(message))
        asyncio.create_task(Queue.updatePic())

        while nameQueue:
            await asyncio.sleep(0.25)

            # Die Queue kann durch stop während des Sleeps geleert worden sein.
            if not nameQueue or not urlQueue:
                return

            if voice_client.is_paused():
                continue

            if not isSkipped and voice_client.is_playing():
                continue

            if isSkipped:
                voice_client.stop()
                isSkipped = False

            if isSongLooped:
                player = await create_player()
                if player is None:
                    return
                voice_client.play(player)
                continue

            if isPlaylistLooped:
                # Aktuellen Titel ans Ende verschieben.
                nameQueue.append(nameQueue.pop(0))
                thumbnailQueue.append(thumbnailQueue.pop(0))
                linkQueue.append(linkQueue.pop(0))
                urlQueue.append(urlQueue.pop(0))
            else:
                # Aktuellen Titel aus der FIFO-Queue entfernen.
                nameQueue.pop(0)
                thumbnailQueue.pop(0)
                linkQueue.pop(0)
                urlQueue.pop(0)

            # Der letzte Titel ist fertig.
            if not urlQueue:
                return

            player = await create_player()
            if player is None:
                return


            voice_client.play(player)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1):
        super().__init__(source, volume)
        self.data = data

    @classmethod
    async def add_playlist_entry(
            cls,
            data,
            author,
            fromNightcore=False
    ):
        global urlQueue
        global linkQueue
        global nameQueue
        global thumbnailQueue
        global nightcoreQueue
        global isNightcore

        if data is None:
            return

        video_id = data.get("id")

        url = data.get("webpage_url")

        if not url:
            url = data.get("url")

        # Bei flat playlists liefert yt-dlp manchmal nur eine ID
        if not url or not str(url).startswith("http"):
            if video_id:
                url = (
                    f"https://www.youtube.com/watch?v={video_id}"
                )
            else:
                return

        name = data.get("title", "Unbekannter Titel")

        thumbnail = data.get("thumbnail")

        if not thumbnail and video_id:
            thumbnail = (
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            )

        urlQueue.append(url)

        # Übergangsweise, damit dein bestehender Code
        # mit linkQueue weiter funktioniert.
        linkQueue.append(url)

        nameQueue.append(
            name + " @" + author
        )

        thumbnailQueue.append(thumbnail)

        if isNightcore and not fromNightcore:
            nightcoreQueue.append(
                name + " @" + author
            )

        print(
            f"[PLAYLIST] Hinzugefügt: {name}"
        )

    @classmethod
    async def load_playlist_background(
            cls,
            entries,
            author,
            fromNightcore=False
    ):
        iterator = iter(entries)

        while True:

            # next() ebenfalls aus dem Eventloop herausnehmen,
            # weil yt-dlp beim Lazy-Iterator Arbeit machen kann
            entry = await asyncio.to_thread(
                next,
                iterator,
                None
            )

            if entry is None:
                break

            try:
                await cls.add_playlist_entry(
                    entry,
                    author,
                    fromNightcore
                )

            except Exception as e:
                print(
                    "[PLAYLIST ENTRY ERROR]",
                    type(e).__name__,
                    str(e)
                )

            # Eventloop kurz freigeben
            await asyncio.sleep(0)

        print("[PLAYLIST] Komplett eingelesen")

    @classmethod
    async def add_song_to_queue(
            cls,
            entries,
            author,
            isPlaylist=False,
            fromNightcore=False
    ):
        global linkQueue
        global nameQueue
        global thumbnailQueue
        global urlQueue
        global nightcoreQueue
        global isNightcore

        # Immer eine Liste daraus machen
        if isPlaylist:
            items = entries
        else:
            if isinstance(entries, list):
                if not entries:
                    return
                items = [entries[0]]
            else:
                items = [entries]

        for data in items:

            if not data:
                continue

            video_id = data.get("id")

            # Normale YouTube-Seite ermitteln
            webpage_url = (
                    data.get("webpage_url")
                    or data.get("original_url")
            )

            # Bei flat-playlist gibt yt-dlp manchmal nur ID / url zurück
            if not webpage_url:

                possible_url = data.get("url")

                if (
                        possible_url
                        and isinstance(possible_url, str)
                        and possible_url.startswith("http")
                ):
                    webpage_url = possible_url

                elif video_id:
                    webpage_url = (
                        f"https://www.youtube.com/watch?v={video_id}"
                    )

            if not webpage_url:
                print(
                    "[QUEUE ERROR] Keine URL für:",
                    data.get("title")
                )
                continue

            name = data.get("title") or "Unbekannter Titel"

            thumbnail = data.get("thumbnail")

            # Fallback
            if not thumbnail and video_id:
                thumbnail = (
                    f"https://i.ytimg.com/vi/"
                    f"{video_id}/hqdefault.jpg"
                )

            # Normale Video-URL
            urlQueue.append(webpage_url)

            # linkQueue wird von deinem alten Code noch erwartet.
            # Direkte Stream-URL speichern wir NICHT mehr.
            linkQueue.append(webpage_url)

            nameQueue.append(
                name + " @" + author
            )

            thumbnailQueue.append(
                thumbnail
            )

            if isNightcore and not fromNightcore:
                nightcoreQueue.append(
                    name + " @" + author
                )

            print(
                f"[QUEUE] Hinzugefügt: {name}"
            )

        print(
            f"[QUEUE] Aktuell {len(nameQueue)} Titel"
        )

    @classmethod
    async def getPlayer(
            cls,
            url,
            filename=None,
            *,
            loop=None
    ):
        print(
            f"[PLAYER] Extrahiere Stream: {url}"
        )

        data = await asyncio.to_thread(
            ytdl_single.extract_info,
            url,
            download=False
        )

        if data is None:
            raise RuntimeError(
                "yt-dlp hat keine Daten geliefert"
            )

        # Falls yt-dlp doch entries liefert
        if "entries" in data:

            entries = [
                entry
                for entry in data["entries"]
                if entry is not None
            ]

            if not entries:
                raise RuntimeError(
                    "Keine gültigen Entries"
                )

            data = entries[0]

        # Jetzt erst die echte Audio-Stream-URL holen
        stream_url = data["url"]

        if not stream_url:
            raise RuntimeError(
                "yt-dlp hat keine Stream-URL geliefert"
            )

        print(
            "[PLAYER] Starte:",
            data.get("title")
        )

        source = discord.FFmpegPCMAudio(
            stream_url,
            **ffmpeg_options
        )

        return cls(
            source,
            data=data
        )

    @classmethod
    async def getUrlInfos(
            cls,
            url,
            author,
            message,
            fromNightcore=False,
            isPlaylist=False,
            *,
            loop=None
    ):
        loop = loop or asyncio.get_running_loop()

        try:

            # =========================
            # PLAYLIST
            # =========================

            if isPlaylist:

                playlist_id = get_playlist_id(url)

                if not playlist_id:
                    print("[PLAYLIST] Keine Playlist-ID gefunden")
                    return

                # Aus:
                #
                # watch?v=XXX&list=PLXXX
                #
                # machen wir:
                #
                # playlist?list=PLXXX

                extract_url = (
                    "https://www.youtube.com/playlist"
                    f"?list={playlist_id}"
                )

                extractor = ytdl_playlist

                print(
                    f"[PLAYLIST] Lade Playlist: "
                    f"{playlist_id}"
                )

            # =========================
            # EINZELNER SONG
            # =========================

            else:

                extract_url = url
                extractor = ytdl_single

                print(
                    f"[SONG] Lade: {extract_url}"
                )

            # yt-dlp nicht im asyncio Eventloop ausführen
            data = await loop.run_in_executor(
                None,
                lambda: extractor.extract_info(
                    extract_url,
                    download=False
                )
            )

        except Exception as e:

            print("[YTDLP ERROR]")
            print(type(e).__name__, str(e))

            return

        if data is None:
            print("[YTDLP] Keine Daten erhalten")
            return

        # ============================================
        # PLAYLIST VERARBEITEN
        # ============================================

        if isPlaylist:

            entries = data.get(
                "entries",
                []
            )

            iterator = iter(entries)

            # ====================================
            # ERSTEN TITEL SOFORT HOLEN
            # ====================================

            first_entry = await asyncio.to_thread(
                next,
                iterator,
                None
            )

            if first_entry is None:
                print("[PLAYLIST] Leer")
                return

            await cls.add_playlist_entry(
                first_entry,
                author,
                fromNightcore
            )

            print(
                "[PLAYLIST] Erster Titel bereit"
            )

            # ====================================
            # REST IM HINTERGRUND
            # ====================================

            asyncio.create_task(
                cls.load_playlist_background(
                    iterator,
                    author,
                    fromNightcore
                )
            )

            return

        # ============================================
        # EINZELNEN SONG VERARBEITEN
        # ============================================

        if "entries" in data:

            entries = [
                entry
                for entry in data.get("entries", [])
                if entry is not None
            ]

            if not entries:
                print("[SONG] Keine Entries gefunden")
                return

            # Bei einem Mix etc. nur ersten Song benutzen
            data = entries[0]

        await cls.add_song_to_queue(
            data,
            author,
            False,
            fromNightcore=fromNightcore
        )

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

    async def setup_hook(self):
        self.ytdlp_worker_task = asyncio.create_task(
            ytdlp_worker()
        )

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

        if "potatoetyl" in str(message.author):
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
                embed.add_field(name="Spaß mit einer Kartoffel", value="pot chat [nachricht] - sprich mit einer lebenden "
                                                                       "Kartoffel :P\npot w2g - der Link zu einem "
                                                                       "kartoffel-starken Watch2Gether-Room", inline=True)
                embed.add_field(name="Einstellungen", value="pot setup - lass die Kraft der Kartoffel frei", inline=True)
                embed.add_field(name="Musik-Befehle", value="pot play [url] - Lass die Kartoffel bei dir spawnen und "
                                                            "deine Ohren mit wundervollen Klängen beschallen \npot "
                                                            "stop - Halte die Kartoffel auf, bevor sie dich in ihren "
                                                            "Ban reißt \npot pause - Bitte die Kartoffel kurz zu "
                                                            "warten \npot resume - Lass die Kartoffel fortfahren\npot "
                                                            "move [titelnummer] [titelnummer] - Wechsel deine Titel "
                                                            "untereinander\npot loop - Die Kartoffel beschallt deine "
                                                            "Ohren Non-Stop mit deinem Lieblingslied\npot skip - Die "
                                                            "Kartoffel beschützt dich vor schlechten Songs\npot "
                                                            "remove [titelnummer] - wenn du die Kartoffel nett fragst, "
                                                            "dann entfernt sie bestimmt das doofe Lied\npot counter - "
                                                            "Gibt dir die Größe der Kartoffel aus\npot get_song ["
                                                            "titelnummer] - Gibt dir den Song der Titelnummer aus\n"
                                                            "pot get_ip - gibt dir die Adresse zu allen Kartoffeln ", inline=False)
                potato = await message.channel.send(embed=embed)
                await client.delete_message(message)
                await asyncio.sleep(10)
                await client.delete_message(potato)

            #Chat-Befehl
            elif "chat" in message_str: #TODO: integrate Deepseek LLM
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
                file = open("/root/bot/guild.txt", 'w')
                file.write(str(message.guild.id))
                file.close()
                channels = await guild.create_text_channel('kartoffel_songrequest')
                channel_id = channels.id
                channel_send = client.get_channel(channel_id)
                embed = discord.Embed(
                    title="No song playing currently",
                    colour=discord.Colour.dark_orange()
                )
                embed.set_image(url=POTATO_IMAGE_URL)
                messages = await channel_send.send(embed=embed)
                message_id = messages.id
                file = open("/root/bot/message_id.txt", 'w')
                file.write(str(message_id))
                file.close()
                file = open("/root/bot/channel_id.txt", 'w')
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

            # Play-Befehl
            elif message_str.startswith("pot play"):
                query = message_str[len("pot play"):].strip()

                if not query:
                    await message.channel.send("Bitte gib einen Titel oder eine URL an.")
                    return

                voice_client = await client.join(message)
                if voice_client is None:
                    return

                author = str(message.author).split("#")[0]
                is_playlist = is_real_youtube_playlist(query)

                await ytdlp_request_queue.put({
                    "url": query,
                    "author": author,
                    "is_playlist": is_playlist,
                    "fromNightcore": False
                })

                await client.delete_message(message)

                # Wenn schon Musik läuft, übernimmt nur der Worker das Queueing.
                if voice_client.is_playing() or voice_client.is_paused():
                    return

                # Beim ersten Titel warten wir nur darauf, dass der Worker
                # den ersten Queue-Eintrag bereitstellt.
                while not urlQueue:
                    await asyncio.sleep(0.05)

                await Queue.control(self, voice_client, message)

            #Stop-Befehl
            elif "stop" in message_str:
                voice_client2 = message.guild.voice_client

                if voice_client2 is not None:
                    voice_client2.stop()

                linkQueue.clear()
                urlQueue.clear()
                nameQueue.clear()
                thumbnailQueue.clear()

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
                        description="Die Größe dieser Kartoffel beträgt: " + str(len(nameQueue)),
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
                    description="https://www.watch2gether.com/rooms/2xpb6xtz4aic2hku6o?lang=de",
                    colour=discord.Colour.dark_orange()
                )
                potato = await message.channel.send(embed=embed)
                await asyncio.sleep(5)
                await client.delete_message(potato)

            elif "get_ip" in message_str:
                await client.delete_message(message)

                ipPublic = get_public_ipv4()

                embed = discord.Embed(
                    description=ipPublic,
                    colour=discord.Colour.dark_orange()
                )

                potato = await message.channel.send(
                    embed=embed
                )

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
        if message.channel is discord.utils.get(message.guild.channels, name="kartoffel_songrequest") and "pot playlist" not in message.content:
            if "pot " in message.content or str(message.author) == "potatoetyl":
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
                is_playlist = is_real_youtube_playlist(url)



                if voice_client is None:
                    print("Voice-Verbindung konnte nicht hergestellt werden.")
                    return

                await ytdlp_request_queue.put({
                    "url": url,
                    "author": author,
                    "is_playlist": is_playlist,
                    "fromNightcore": False
                })

                if isNightcore:
                    asyncio.create_task(YTDLSource.getNightcore(message))

                await client.delete_message(message)

                # Ein laufender Player verarbeitet die neue Queue später selbst.
                if voice_client.is_playing() or voice_client.is_paused():
                    return

                # Erster Request: warten, bis der Worker mindestens einen
                # spielbaren Eintrag erzeugt hat.
                while not urlQueue:
                    await asyncio.sleep(0.05)

                await Queue.control(self, voice_client, message)


    async def delete_message(self, message):
        await asyncio.sleep(1)
        await message.delete()

    async def join(self, message):
        if message.author.voice is None:
            await message.channel.send("Du bist in keinem Voice-Channel.")
            return None

        channel = message.author.voice.channel

        try:
            voice_client = message.guild.voice_client

            # Bot ist bereits irgendwo verbunden
            if voice_client is not None and voice_client.is_connected():
                if voice_client.channel != channel:
                    await voice_client.move_to(channel)

                return voice_client

            # Neu verbinden
            print(f"Verbinde mit Voice-Channel: {channel}")
            voice_client = await channel.connect()

            print(f"Voice verbunden: {voice_client.is_connected()}")
            return voice_client

        except Exception as e:
            print("VOICE CONNECT ERROR:")
            print(type(e).__name__, str(e))
            return None

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
                if voice_client2 is not None:
                    voice_client2.stop()

                linkQueue.clear()
                urlQueue.clear()
                nameQueue.clear()
                thumbnailQueue.clear()

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
                        asyncio.create_task(YTDLSource.getNightcore(message, first=True))
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
	with open("/root/bot/message_id.txt") as f:
		m = f.read()
		if m != "":
			messageId = m
except:
	print("Problem 1")

try:
    with open("/root/bot/channel_id.txt") as f:
        m = f.read()
        if m != "":
            channel_id = m
except:
    print("Problem 2")



Intents = discord.Intents().all()
client = MyClient(intents=Intents)

token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    raise RuntimeError("DISCORD_BOT_TOKEN ist nicht gesetzt")

client.run(token)
