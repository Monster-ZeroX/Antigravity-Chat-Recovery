# Antigravity IDE Chat Recovery Toolkit

A complete, open-source toolkit to securely back up your chat history, clear corrupted update caches, and restore orphaned conversation workspaces in the Antigravity AI IDE.

If your Antigravity IDE recently forced an auto-update and wiped your sidebar history, or if your local chats are hidden because they lost their workspace mappings, this kit will securely rebuild your database and recover your work.

## ⚠️ The Problem: The Migration Bug
During the forced migration to the 2.0 Manager View, the Antigravity architecture abandoned its classic folder structure, changing system folders from `antigravity` to `Antigravity IDE` and `.gemini/antigravity` to `.gemini/antigravity-ide`.

Because of this oversight, the built-in SQLite database (`state.vscdb`) that links your local `.pb` chat files to your specific project folders gets completely broken. The IDE thinks your chats don't belong to your current workspace, so it permanently hides them from the UI.

## 🛠️ Features
- **Smart Backup:** Safely extracts your raw protobuf chat logs and user settings across both legacy and modern folder architectures.
- **Deep Purge:** Forcibly clears corrupted `globalStorage` and `workspaceStorage` links that hide your chats.
- **Clean Restore:** Injects your chat data back into the correct modern system directories while intentionally skipping corrupted database files.
- **Update Blocker:** Automatically injects settings to prevent aggressive background auto-updaters from hijacking your IDE again.
- **Python Fixer:** Rebuilds the IDE's SQLite database from scratch and allows you to manually re-map orphaned chats to your local project folders.

## 📋 Prerequisites
- **OS:** Windows (Batch scripts are Windows-specific, the Python script is cross-platform).
- **Python:** Python 3.7+ installed and added to your system PATH.

---

## 🚀 Step-by-Step Recovery Guide

### Phase 1: Secure & Purge
1. **Back up your data:** Double-click `1_backup.bat`. This will automatically pull your raw chats and settings into a new `AG_Backup` folder located in the same directory as the script.
2. **Uninstall Antigravity:** Remove the current corrupted version of the IDE from your Windows settings.
3. **Purge the cache:** Double-click `2_purge.bat`. This destroys the hidden AppData payload and corrupted caches that are causing the UI loops.

### Phase 2: The Offline Blackout (Critical)
4. **DISCONNECT FROM THE INTERNET.** (If the installer detects Wi-Fi for even a second, it will instantly fetch the broken update payload again).
5. Install your preferred/legacy version of the Antigravity IDE.
6. Open the IDE, let it sit on the "No Internet" welcome screen for exactly **10 seconds** (this allows the IDE to generate a fresh, uncorrupted database in the background), and then completely close the application.

### Phase 3: Restore & Map
7. **Restore your data:** Double-click `3_restore.bat`. This moves your raw chats back into the new system architecture and applies an update-blocker to your settings.
8. **Fix the database:** Open your terminal in the repository folder and run the python script:

```bash
python fix_chats.py
```

When prompted by the script, press 2 to manually map your recovered conversations to their respective local project folders.

Reboot your PC, turn your internet back on, and open Antigravity. Open your project folders, and your history will be fully restored in the sidebar.

📂 Repository Contents
1_backup.bat - Safely copies data to a local AG_Backup folder.

2_purge.bat - Clears corrupted IDE memory, caches, and staged update payloads.

3_restore.bat - Restores raw chats to the modern folder structure and blocks updates.

fix_chats.py - Parses raw .pb files, extracts context, and rewrites the Antigravity SQLite database to link your chats to your workspaces.
# Antigravity-Chat-Recovery
complete recovery toolkit for the Antigravity IDE. Safely extract local .pb chat histories, repair broken SQLite workspace links, and restore missing sidebar conversations after an IDE update.
