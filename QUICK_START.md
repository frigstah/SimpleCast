# SimpleCast quick start

This guide is for first-time users. You do not need to understand audio
engineering to start broadcasting.

## Before you begin

You need:

- A Windows 10 or Windows 11 computer
- A microphone, mixer, or other recording device
- The server address, port, source password, and stream path or SID supplied by
  your radio host

If your host has not sent those connection details, ask them for the settings
for an **Icecast or SHOUTcast source encoder**.

## 1. Install or open SimpleCast

The installer is easiest for most people. The portable ZIP does not install
anything: extract the entire folder before opening `SimpleCast.exe`.

This beta is not digitally signed, so Windows may show an unknown-publisher or
SmartScreen warning. Download only from the official SimpleCast GitHub release
and compare the file with the published SHA-256 checksum. If Windows offers
**More info → Run anyway**, continue only after you have verified the download.

## 2. Choose your sound

On the **Dashboard**:

1. Open the **Device** list.
2. Choose the microphone, mixer, or line input you want to broadcast.
3. Leave **Audio system** on **Automatic** at first. SimpleCast normally chooses
   Windows WASAPI shared mode.
4. Speak or play audio and watch the **L** and **R** meters.
5. Adjust **Input volume** until the meters move clearly without spending much
   time in red.

If the meters do not move, choose another device and press **Refresh**.

## 3. Test your sound

1. Press **Test my sound**.
2. Speak or play music for five seconds.
3. Use **Play original** to hear the captured signal.
4. Choose a **Processing** preset and use **Play processed** to hear what will
   be sent.

Good starting choices:

- **Off / Original** — no processing
- **Voice** — speech and talk radio
- **Music** — gentle control for music
- **Mixed content** — speech, jingles, and music together

## 4. Add your radio server

1. Press **Manage stations**.
2. Press **+ Add station**.
3. Choose **Icecast 2**, **SHOUTcast 1**, or
   **SHOUTcast 2 (compatible source)**.
4. Enter the details from your radio host.
5. Press **Save station**.

Common Icecast fields:

- **Server address:** for example `radio.example.com`
- **Port:** for example `8000`
- **Stream path:** for example `/live`
- **Source username:** commonly `source`
- **Source password:** supplied by your host

For SHOUTcast, enter the port and source password. SHOUTcast 2 may also require
a **Stream ID (SID)**.

Use **Test** when the station is not already receiving a live source. The test
briefly opens the stream connection, so do not test a mount or SID that is
currently on air.

## 5. Add favorite stations

SimpleCast can show up to six favorites on the Dashboard:

1. Open **Manage stations**.
2. Select a station.
3. Press **★ Favorite**.
4. Repeat for up to six stations.

Clicking a favorite tile on the Dashboard makes it the destination for the next
broadcast. A check mark shows the selected favorite.

To broadcast to several servers at the same time, use **Manage stations** and
mark each required server as **Included**.

## 6. Choose stream quality

For most broadcasts, use:

- **SL Standard:** MP3 at 128 kbps
- **48 kHz:** a common sample rate for broadcasting

**SL MAX unsafe** uses 192 kbps and may exceed the limit of some hosting plans.
**Recording** uses 320 kbps and requires more bandwidth.

## 7. Send the artist and title

In **Now Playing**:

1. Type the artist into **Artist**.
2. Type the song or programme name into **Title**.
3. Press **SEND NOW PLAYING**.

SimpleCast sends the text as `Artist - Title` to the selected Icecast or
SHOUTcast server. This does not identify songs automatically; you control
exactly what listeners see.

An optional text-file integration is available under **Settings** for radio
automation software that already writes now-playing information to a file.

## 8. Start broadcasting

Before going live, check that:

- The correct favorite or included station is selected
- The audio meters are moving
- The quality and sample rate are correct
- The server connection test has passed

Press **START BROADCAST**. The status changes while SimpleCast connects and then
shows **ON AIR**. To finish, press **STOP BROADCAST** and confirm.

### See your live listeners and personal best

While a station is on air, SimpleCast checks its public listener statistics
about every 10 seconds. The station row shows:

- **Live listeners:** the latest count reported by the server
- **Personal best:** the highest count SimpleCast has seen for that saved station

The personal best is kept after SimpleCast closes and is also shown for every
saved station under **Manage stations**. Because the count is sampled, a very
short listener spike between checks may not be recorded. If a radio host blocks
public statistics, SimpleCast shows **unavailable** and keeps broadcasting
normally.

## Optional recording

Open **Recordings** in the sidebar to:

- Choose where recordings are saved
- Record every broadcast automatically
- Make a local 320 kbps MP3 without broadcasting

## If something does not work

### No audio on the meters

- Press **Refresh** and choose the device again.
- Leave the audio system on **Automatic**.
- Close other software that may have exclusive control of the device.
- Reconnect a USB mixer or microphone, then restart SimpleCast.

### The connection test passes but broadcasting fails

- Make sure another encoder is not already using the same mount or SID.
- Check that the source password—not the listener or administrator password—is
  saved.
- Confirm the server type, port, stream path, and SID with your host.

### SimpleCast reports clipping

Lower **Input volume** or reduce the level on the mixer. Processing can control
normal peaks, but it cannot repair audio that was already badly clipped.

### You need help

Under **Settings**, run **Run readiness check**. You can also choose
**Export support report** and inspect the report before sharing it. SimpleCast
stores its log at:

`%LOCALAPPDATA%\SimpleCast\simplecast.log`

Never post your source password publicly.
