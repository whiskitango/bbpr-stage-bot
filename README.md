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

### The log file

`docker compose logs` is lost whenever the container is made again (`--build`, or after changing `.env`).
So the bot also keeps its log in a file in the data volume, with the time (UTC) on every line. It keeps
the newest 10 MB plus five older files of 10 MB, then drops the oldest.

```
docker compose exec stage-bot tail -n 200 /data/logs/stagebot.log      (the latest lines)
docker compose exec stage-bot grep -h "no audio\|stream ended\|speaker\|lost" /data/logs/stagebot.log*
docker compose cp stage-bot:/data/logs/stagebot.log .                   (a copy here, even if it's stopped)
```

**If it goes silent**, look for these lines:

| Line | What happened |
|---|---|
| `[player] no audio from the stream for 10 s` | The station's stream stalled. The bot reopens it by itself; every server was quiet meanwhile |
| `[player] stream ended; reopening` / `[ffmpeg] …` | The stream dropped, or ffmpeg failed |
| `[stage] could not become a speaker in …` | That Stage only: the bot is in the audience. Make it a Stage moderator |
| `[stage] lost …` / `not connected …; rejoining` | That server's voice connection dropped |

With `VOICE_DEBUG=yes` the bot also logs, every 15 s per channel, how many audio packets it sent and how many
were silence: `packets` climbing means audio is going out; `silent` climbing means it has nothing to send.

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
| `VOLUME` | no | How loud it plays, as a % of the station's level: 1 to 100, 50 by default. The station is loud and Discord plays a bot at full volume, so full level blasts a Stage when the bot joins |
| `DATA_DIR` | no | Where joined channels and the log file (`logs/stagebot.log`) are saved |
| `FFMPEG_PATH` | no | A specific ffmpeg to use |
| `STATUS_PORT` | no | Turns on the listener-count page for radio-metrics (see below) |
| `STATUS_TOKEN` | with `STATUS_PORT` | The password radio-metrics sends, at least 24 characters |
| `STATUS_HOST` | no | Where the page listens. `127.0.0.1` (this machine only) by default |
| `STATUS_TLS_CERT`, `STATUS_TLS_KEY` | no | A certificate and its key, to serve the page over https |
| `STATION` | no | The station's short name the counts are for. Taken from `STREAM_URL` by default |

## Discord counts in radio-metrics

With `STATUS_PORT` set, the bot answers `GET /status` with how many people are listening in each
channel it plays in. The count includes speakers and the audience, but not bots or anyone who has
deafened themselves. `servers` is how many servers have the bot installed, whether it plays there or not.
Only an `Authorization: Bearer <STATUS_TOKEN>` request gets an answer.

```json
{ "station": "booty_bay_pirate_radio", "at": 1790000000000, "listeners": 5, "servers": 3,
  "channels": [{ "server": "Pirates", "channel": "Radio Room", "kind": "stage", "playing": true, "listeners": 5 }] }
```

In radio-metrics, go to Settings → Alerts → Discord Stage bot and enter the address and the token.

radio-metrics sends the token over plain http only to its own PC or the local network. So, for the bot on the
AzuraCast server, use one of these:

- **https:** set `STATUS_HOST=0.0.0.0`, point `STATUS_TLS_CERT`/`STATUS_TLS_KEY` at a certificate
  for the server's name, open the port in the firewall, and enter `https://your.server:8790`. A renewed
  certificate is picked up within a few hours without a restart.
- **SSH tunnel:** leave the page on `127.0.0.1`, run `ssh -N -L 8790:127.0.0.1:8790 you@your.server`
  on the PC, and enter `http://127.0.0.1:8790`.

## Good to know

- **Royalty and stats counts.** AzuraCast sees the bot as **one** listener, however many people
  and servers are listening through it. So the station's listener numbers and the SoundExchange
  report undercount Discord listeners. radio-metrics can show the Discord count beside them
  (see *Discord counts in radio-metrics*).
- **Ending the Stage.** If a moderator ends the Stage while the bot is in it, the bot keeps playing in
  the channel and opens the Stage again the next time it joins. To take it off air on a server, use `/radio leave`.
- **Deleted channels.** If a channel is deleted, or the bot loses access to it, the bot gives up on it and forgets it.

## Tests

```
npm test
```
