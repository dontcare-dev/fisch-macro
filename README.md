# Fish Macro

Windows desktop GUI for screen-based Fisch fishing automation.

## Automation
- Holds and releases the cast input instead of sending a blind click.
- Detects the moving SHAKE prompt using a user-captured screen template and clicks it wherever it appears inside the scan region.
- Detects the moving fish marker with live template matching.
- Finds the white reel slider from the live screen, measures its current width, tracks fish movement between frames, predicts a short distance ahead, and switches between mouse hold and release to keep the fish inside the slider.
- Uses the actual on-screen slider width, so different rod control widths are measured from the game rather than assumed from a rod name.
- Automatically repeats the cast / catch cycle when enabled.
- Uses screen capture and simulated mouse input only. No Roblox memory reading, process inspection, DLL injection, or game modification.

## Other features
- Searchable rod catalog with stats, availability filters and selected-rod profiles.
- Catalog refresh from a public Fisch rod reference; offline fallback included.
- Rod artwork lookup through the Fisch wiki image API when an indexed image is available.
- Configurable global hotkey (F12 by default).
- Configurable screen scan region, cast coordinates, matching threshold, scan interval, and recast delay.

## Run from source
1. Install Python 3.11 or newer.
2. Run python -m pip install -r requirements.txt.
3. Run python main.py.

## Build
Run build.bat, or use the GitHub Actions workflow to build a Windows executable.

## First-time setup
1. Open Fisch at the screen size and display scale you plan to use.
2. In Settings, set the cast click position and a scan region that contains the SHAKE prompt and the full reel minigame.
3. Choose Capture SHAKE prompt. After the message closes, switch to Fisch within three seconds and select a tight crop around the SHAKE button.
4. Choose Capture moving fish marker. Start a reel minigame, switch to Fisch within three seconds, and select a tight crop around the moving fish icon/marker (not the whole reel bar).
5. Save settings and test with the game visible. Press F12 (or the configured hotkey) to start or stop.

The macro uses visual templates and screen geometry. If the game changes its UI, display scale, or marker appearance, recapture the templates. The live controller uses the detected slider width and fish movement; it does not read game memory. Screen-based detection can still fail if the marker is obscured, the scan region is wrong, or the UI differs from the captured templates.

## Rod data
The built-in list is an offline fallback. Use Update catalog in the Rods tab to retrieve the latest rows from the linked public rod reference. Stats and availability may change with game updates. Artwork appears when the Fisch wiki image API has an indexed image for that rod.

## Safety
Use only in accordance with the game's current rules. The macro uses screen capture and simulated mouse clicks only.