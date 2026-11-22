# Fish Macro

Windows desktop GUI for screen-based Fisch fishing automation.

## Features
- Searchable rod catalog with stats, availability filters and selected-rod profiles.
- Catalog refresh from a public Fisch rod reference; offline fallback included.
- Rod artwork lookup through the Fisch wiki image API when an indexed image is available.
- Configurable global hotkey (F12 by default).
- Screen capture + OpenCV template matching for a user-captured visual bite prompt.
- Configurable cast coordinates, scan region, match threshold and recast delay.
- No Roblox memory reading, process inspection, DLL injection or game modification.

## Run from source
1. Install Python 3.11 or newer.
2. Run `python -m pip install -r requirements.txt`.
3. Run `python main.py`.

## Build
Run `build.bat`, or use the GitHub Actions workflow to build a Windows executable.

## First-time setup
1. Open Fisch at a consistent window size and display scale.
2. Set cast click coordinates and a small scan region around the visual bite prompt.
3. Capture the prompt template while it is visible.
4. Test the detection and adjust the image-match threshold as needed.
5. Press the configured hotkey (F12 by default) to start or stop.

The macro uses image matching and simulated mouse clicks. The game's UI can change, so the visual template and coordinates may need to be recaptured after updates. This initial version automates the cast / visual prompt detection loop; it does not claim to solve every reel minigame state.

## Rod data
The built-in list is an offline fallback. Use **Update catalog** in the Rods tab to retrieve the latest rows from the linked public rod reference. Stats and availability may change with game updates. Artwork appears when the Fisch wiki image API has an indexed image for that rod.

## Safety
Use only in accordance with the game's current rules. The macro uses screen capture and simulated mouse clicks only.
