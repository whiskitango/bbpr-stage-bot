# BBPR Stage Bot

A Discord bot that plays the radio station on a Stage (or a plain voice
channel), so people can listen without leaving Discord. It:

- plays on as many servers as you allow, one channel each, all from one stream
- joins with `/radio join`, which only people with **Manage Channels** can use
- opens the Stage if nobody has, and steps up to speaker
- reopens the stream if it drops, and rejoins after a network drop or a Discord restart
- shows the song on air in each Stage's topic and as its "Listening to" status

## 1. Make the bot in Discord

1. Go to <https://discord.com/developers/applications> and click **New Application**. Name it, for example *BBPR Radio*.
2. Open **Bot**, click **Reset Token** and copy the token. It's a password, so keep it secret.
   No privileged intents are needed.
3. On the same **Bot** page, turn **Public Bot** off. Then only you can add it to servers.
4. Open **OAuth2 → URL Generator** and tick the scopes **bot** and **applications.commands**. Then tick the permissions
   **View Channels**, **Connect** and **Speak**. Open the link it gives you and add the bot to a server.
5. On each server, make the bot a Stage moderator so it can start the Stage and speak without
   anyone accepting it. Open the Stage channel's settings, go to **Permissions** and add the bot (or its role)
   as a **Stage Moderator**.
6. Put the server's ID in `ALLOWED_GUILD_IDS`. Turn on Developer Mode (User Settings → Advanced),
   then right-click the server icon → **Copy Server ID**.

## 2. Use it

In a server, anyone with **Manage Channels** can use:

| Command | What it does |
|---|---|
| `/radio join` | Plays in the Stage you're in, or the one you pick with `channel:` |
| `/radio leave` | Stops playing on this server |
| `/radio status` | Says where it's playing |

**Who can use it.** Discord hides `/radio` from members without Manage Channels and refuses it
if they try. To let a particular role use it instead, go to **Server Settings → Integrations → the bot → /radio**.
The bot doesn't check again itself, because that would undo the choice you make there.
Replies are seen only by whoever used the command. It doesn't work in DMs.

**Which servers.** With `ALLOWED_GUILD_IDS` set, `/radio` is refused on any other server,
even if someone manages to add the bot there.

Channels it joins are saved in `data/channels.json` and rejoined after a restart.

## 3. Run it on your PC (to try it)

Needs Node 22.12 or newer.

```
npm install
copy .env.example .env      (then fill in .env)
npm start
```

`npm install` downloads its own ffmpeg, so nothing else needs installing.
Press Ctrl+C to stop; the bot leaves the Stage.
Only one copy runs at a time. A second start says the bot is already running.

## 4. Run it on the server (always on)

On your PC the Stage goes quiet when the PC is off. On the AzuraCast server, with Docker:

```
docker compose up -d --build
docker compose logs -f        (to watch it start)
```

`restart: unless-stopped` brings it back after a reboot, and the saved channels live in a Docker volume.

## Settings (.env)

| Setting | Needed | What it is |
|---|---|---|
| `DISCORD_TOKEN` | yes | The bot's token |
| `ALLOWED_GUILD_IDS` | strongly advised | Servers it may play on, comma-separated. Empty means any server it's in |
| `STAGE_CHANNEL_ID` | no | Channels to join at start, comma-separated, as well as those saved by `/radio join` |
| `STREAM_URL` | no | The stream to play. Defaults to the station's 256 kbps MP3 |
| `NOW_PLAYING_URL` | no | AzuraCast's now-playing API for the topic. Set it to nothing to turn this off |
| `STAGE_TOPIC` | no | The Stage's name. Defaults to *Booty Bay Pirate Radio* |
| `BITRATE` | no | Kbps sent to Discord, 128 by default (Discord plays up to the server's voice bitrate) |
| `DATA_DIR` | no | Where joined channels are saved |
| `FFMPEG_PATH` | no | A specific ffmpeg to use |

## Good to know

- **Royalty and stats counts.** AzuraCast sees the bot as **one** listener, however many people
  and servers are listening through it. So the station's listener numbers and the SoundExchange
  report undercount Discord listeners.
- **Ending the Stage.** If a moderator ends the Stage while the bot is in it, the bot keeps playing in
  the channel and opens the Stage again the next time it joins. To take it off air on a server, use `/radio leave`.
- **Deleted channels.** If a channel is deleted, or the bot loses access to it, the bot gives up on it and forgets it.

## Tests

```
npm test
```
