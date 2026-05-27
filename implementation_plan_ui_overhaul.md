# Implementation Plan for UI Overhaul

## Goal Description

Refactor the EDITH full‑screen user interface:
- Adjust transparent/overlay colours for a cleaner premium look.
- Ensure the UI works consistently in both full‑screen and compact modes.
- Add a clearly labelled **Ayarla** (Settings) button that opens the settings panel.
- expose a **Memory** tab inside the settings panel where users can view, add, edit and delete memory entries via a simple form.
- Make the new memory UI functional and correctly displayed when the tab is selected.

## User Review Required

- Confirm the colour palette for the full‑screen background (if you prefer a different hue).
- Approve the placement and label of the **Ayarla** button.
- Verify the layout size of the Memory tab (panel width/height) is suitable for your screen.

## Open Questions

- Do you want the **Ayarla** button to be always visible on the right‑hand side, or only in compact mode?
- Should the Memory tab include a *search* field for quick lookup, or is the list sufficient?

## Proposed Changes

### [UI] `ui.py`
- Update colour constants for full‑screen overlay (e.g., use semi‑transparent dark panels).
- Modify `_draw_settings_button` to use the label **Ayarla** instead of "SYSTEM SETTINGS".
- Ensure the settings button is always placed at the top‑right corner.
- Add logic in `_place_layout_widgets` to handle the new Memory tab: show `_memory_body` when selected, hide others.
- Adjust panel geometry (`_settings_geometry`) to a slightly larger size for memory content.
- Refactor `_build_memory_controls` to use consistent styling and bind it into the settings panel.
- Ensure `_refresh_memory_listbox` updates after any edit/delete.
- Add a small helper method `_toggle_settings_panel` to focus the Settings panel when **Ayarla** is clicked.

### [Memory] `memory/memory_manager.py`
- No changes required; the UI will call existing `load_memory`, `update_memory`, `delete_memory`.

## Verification Plan

### Automated Tests
- Run the EDITH app, open full‑screen mode, verify the background colour matches the new palette.
- Click the **Ayarla** button, ensure the Settings panel appears.
- Switch to the **Memory** tab, add a new entry, verify it persists in `memory.json`.
- Delete an entry and confirm it's removed.

### Manual Verification
- Visually inspect the UI on a 1080p monitor for proper alignment.
- Test both full‑screen and compact modes.
- Confirm that the Settings button label reads **Ayarla**.
