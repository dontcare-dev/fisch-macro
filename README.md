# Fish Macro

Windows desktop GUI for screen-based Fisch fishing automation.

## Automation
- Automatically casts from one fixed water click point.
- Detects the reel track, moving fish marker and control bar from live screen pixels.
- No screen-template capture, movement recording or movement playback.
- Measures the live bar width and predicts fish movement to control the reel input.
- Waits for Roblox to be the foreground window before sending inputs; it does not send background inputs or bypass AFK rules.
- Automatically repeats the cast / catch cycle when enabled.
- Uses ordinary screen capture and mouse/keyboard input only. No Roblox memory reading, process inspection, DLL injection or game modification.

The live detector is experimental and may need tuning for different display scales, themes, rod effects and Fisch updates. The first setup requires one fixed cast point over water; this is a single coordinate, not a recorded movement path.

## Rod catalog
- Fetches the main searchable rod table from [OofWiki](https://oofwiki.com/fisch/rods).
- Supplements rod names and minigame-relevant stats from a second public rod-data index.
- Includes Seraphic Rod as an offline fallback, with its Seraphic Lord search alias.
- Shows price, lure speed, luck, control, resilience, max weight, location, ability and source when the provider has the field.
- Catalog refresh runs automatically on first launch when the local list is incomplete.

Rod values can differ between sources and game versions. Missing fields are shown as unavailable instead of being invented.

## Other features
- Searchable rod catalog with filters and selected-rod profiles.
- Rod artwork lookup through the Fisch Wiki image API when an indexed image is available.
- Configurable global hotkey (F12 by default).
- Configurable cast point, cast hold, scan interval and recast delay.
- Optional totem slot configuration.

## Run from source
1. Install Python 3.11 or newer.
2. Run `python -m pip install -r requirements.txt`.
3. Run `python main.py`.

## Build
Run `build.bat`, or use the GitHub Actions workflow to build a Windows executable. The build excludes unused Qt modules and optional Python packages.

## First-time setup
1. Open Fisch at the screen size and display scale you plan to use.
2. In Settings, set one fixed cast point over the water.
3. Keep Roblox in the foreground and press F12 (or the configured hotkey). Starting from the GUI waits until Roblox is focused.
4. Keep the game visible while the macro runs.

## Safety
Use only in accordance with the game's current rules. The macro uses screen capture and simulated input only.
