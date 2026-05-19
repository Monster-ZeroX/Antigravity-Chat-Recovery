"""
Antigravity Conversation Fix  (v1.05 - Fully Patched for New Folder Names)
=============================
"""

import sqlite3
import base64
import json
import os
import re
import sys
import time
import subprocess
import platform
from urllib.parse import quote, unquote

# ─── Paths ────────────────────────────────────────────────────────────────────

_SYSTEM = platform.system()

if _SYSTEM == "Windows":
    # Pointing to the new folder names
    DB_PATH = os.path.expandvars(
        r"%APPDATA%\Antigravity IDE\User\globalStorage\state.vscdb"
    )
    CONVERSATIONS_DIR = os.path.expandvars(
        r"%USERPROFILE%\.gemini\antigravity-ide\conversations"
    )
    BRAIN_DIR = os.path.expandvars(
        r"%USERPROFILE%\.gemini\antigravity-ide\brain"
    )
    WORKSPACE_STORAGE_DIR = os.path.expandvars(
        r"%APPDATA%\Antigravity IDE\User\workspaceStorage"
    )
elif _SYSTEM == "Darwin":  # macOS
    _home = os.path.expanduser("~")
    DB_PATH = os.path.join(
        _home, "Library", "Application Support",
        "Antigravity IDE", "User", "globalStorage", "state.vscdb"
    )
    CONVERSATIONS_DIR = os.path.join(
        _home, ".gemini", "antigravity-ide", "conversations"
    )
    BRAIN_DIR = os.path.join(
        _home, ".gemini", "antigravity-ide", "brain"
    )
    WORKSPACE_STORAGE_DIR = os.path.join(
        _home, "Library", "Application Support",
        "Antigravity IDE", "User", "workspaceStorage"
    )
else:  # Linux
    _home = os.path.expanduser("~")
    DB_PATH = os.path.join(
        _home, ".config", "Antigravity IDE",
        "User", "globalStorage", "state.vscdb"
    )
    CONVERSATIONS_DIR = os.path.join(
        _home, ".gemini", "antigravity-ide", "conversations"
    )
    BRAIN_DIR = os.path.join(
        _home, ".gemini", "antigravity-ide", "brain"
    )
    WORKSPACE_STORAGE_DIR = os.path.join(
        _home, ".config", "Antigravity IDE",
        "User", "workspaceStorage"
    )

BACKUP_FILENAME = "trajectorySummaries_backup.txt"

def encode_varint(value):
    result = b""
    while value > 0x7F:
        result += bytes([(value & 0x7F) | 0x80])
        value >>= 7
    result += bytes([value & 0x7F])
    return result or b'\x00'

def decode_varint(data, pos):
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos + 1
        shift += 7
        pos += 1
    return result, pos

def skip_protobuf_field(data, pos, wire_type):
    if wire_type == 0:    
        _, pos = decode_varint(data, pos)
    elif wire_type == 2:  
        length, pos = decode_varint(data, pos)
        pos += length
    elif wire_type == 1:  
        pos += 8
    elif wire_type == 5:  
        pos += 4
    return pos

def strip_field_from_protobuf(data, target_field_number):
    remaining = b""
    pos = 0
    while pos < len(data):
        start_pos = pos
        try:
            tag, pos = decode_varint(data, pos)
        except Exception:
            remaining += data[start_pos:]
            break
        wire_type = tag & 7
        field_num = tag >> 3
        new_pos = skip_protobuf_field(data, pos, wire_type)
        if new_pos == pos and wire_type not in (0, 1, 2, 5):
            remaining += data[start_pos:]
            break
        pos = new_pos
        if field_num != target_field_number:
            remaining += data[start_pos:pos]
    return remaining

def encode_length_delimited(field_number, data):
    tag = (field_number << 3) | 2
    return encode_varint(tag) + encode_varint(len(data)) + data

def encode_string_field(field_number, string_value):
    return encode_length_delimited(field_number, string_value.encode('utf-8'))

def _is_remote_uri(path_or_uri):
    return path_or_uri.startswith("vscode-remote://") or path_or_uri.startswith("file:///")

def path_to_workspace_uri(folder_path):
    if _is_remote_uri(folder_path):
        return folder_path

    p = folder_path.replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        drive = p[0].lower()
        rest = p[2:]
    else:
        drive = None
        rest = p

    segments = rest.split("/")
    encoded_segments = [quote(seg, safe="") for seg in segments]
    encoded_path = "/".join(encoded_segments)

    if drive:
        return f"file:///{drive}%3A{encoded_path}"
    else:
        return f"file:///{encoded_path.lstrip('/')}"

def build_workspace_field(folder_path):
    uri = path_to_workspace_uri(folder_path)
    sub_msg = (
        encode_string_field(1, uri)
        + encode_string_field(2, uri)
    )
    return encode_length_delimited(9, sub_msg)

def extract_workspace_hint(inner_blob):
    if not inner_blob:
        return None
    try:
        pos = 0
        while pos < len(inner_blob):
            tag, pos = decode_varint(inner_blob, pos)
            wire_type = tag & 7
            field_num = tag >> 3
            if wire_type == 2:
                l, pos = decode_varint(inner_blob, pos)
                content = inner_blob[pos:pos + l]
                pos += l
                if field_num > 1:
                    try:
                        text = content.decode("utf-8", errors="strict")
                        if "file:///" in text or "vscode-remote://" in text:
                            return text
                    except Exception:
                        pass
            elif wire_type == 0:
                _, pos = decode_varint(inner_blob, pos)
            elif wire_type == 1:
                pos += 8
            elif wire_type == 5:
                pos += 4
            else:
                break
    except Exception:
        pass
    return None

def load_known_workspace_uris():
    uris = []
    if not os.path.isdir(WORKSPACE_STORAGE_DIR):
        return uris
    try:
        for name in os.listdir(WORKSPACE_STORAGE_DIR):
            ws_json = os.path.join(WORKSPACE_STORAGE_DIR, name, "workspace.json")
            if os.path.exists(ws_json):
                try:
                    with open(ws_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    uri = data.get("folder") or data.get("workspace")
                    if uri:
                        uris.append(uri)
                except Exception:
                    pass
    except Exception:
        pass
    uris.sort(key=len, reverse=True)
    return uris

def _uri_to_local_path(file_uri):
    if not file_uri.startswith("file:///"):
        return None
    raw = unquote(file_uri[len("file://"):])
    if _SYSTEM == "Windows" and len(raw) >= 3 and raw[0] == '/' and raw[2] == ':':
        raw = raw[1:]  
    return raw

def infer_workspace_from_brain(conversation_id, known_ws_uris=None):
    brain_path = os.path.join(BRAIN_DIR, conversation_id)
    if not os.path.isdir(brain_path):
        return None

    if _SYSTEM == "Windows":
        local_pattern = re.compile(r"file:///([A-Za-z](?:%3A|:)/[^)\s\"'\]>]+)")
    else:
        local_pattern = re.compile(r"file:///([^)\s\"'\]>]+)")
    remote_pattern = re.compile(r"(vscode-remote://[^)\s\"'\]>]+)")

    found_uris = []     
    found_remote = []   

    try:
        for name in os.listdir(brain_path):
            if not name.endswith(".md") or name.startswith("."):
                continue
            filepath = os.path.join(brain_path, name)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(16384)

                for match in remote_pattern.finditer(content):
                    found_remote.append(match.group(1))

                for match in local_pattern.finditer(content):
                    found_uris.append("file:///" + match.group(1))
            except Exception:
                pass
    except Exception:
        return None

    if not found_uris and not found_remote:
        return None

    if known_ws_uris:
        ws_counts = {}
        for file_uri in found_uris:
            normalized = file_uri.replace("%3A", ":").replace("%3a", ":")
            normalized = normalized.replace("%20", " ")
            for ws_uri in known_ws_uris:
                ws_norm = ws_uri.replace("%3A", ":").replace("%3a", ":")
                ws_norm = ws_norm.replace("%20", " ")
                if normalized.startswith(ws_norm + "/") or normalized == ws_norm:
                    ws_counts[ws_uri] = ws_counts.get(ws_uri, 0) + 1
                    break 

        for remote_uri in found_remote:
            for ws_uri in known_ws_uris:
                if remote_uri.startswith(ws_uri + "/") or remote_uri == ws_uri:
                    ws_counts[ws_uri] = ws_counts.get(ws_uri, 0) + 1
                    break

        if ws_counts:
            best_ws_uri = max(ws_counts, key=ws_counts.get)
            local = _uri_to_local_path(best_ws_uri)
            if local:
                return local
            return best_ws_uri

    path_counts = {}
    for file_uri in found_uris:
        raw = file_uri[len("file:///"):]
        raw = raw.replace("%3A", ":").replace("%3a", ":")
        raw = raw.replace("%20", " ")
        parts = raw.replace("\\", "/").split("/")
        
        if _SYSTEM == "Windows":
            depth = 5
        else:
            depth = 4
        if len(parts) >= depth:
            ws = "/".join(parts[:depth])
            if _SYSTEM != "Windows" and not ws.startswith("/"):
                ws = "/" + ws
            path_counts[ws] = path_counts.get(ws, 0) + 1

    for remote_uri in found_remote:
        path_counts[remote_uri] = path_counts.get(remote_uri, 0) + 1

    if not path_counts:
        return None

    best = max(path_counts, key=path_counts.get)
    if best.startswith("vscode-remote://"):
        return best
    return best.replace("/", os.sep)

def build_timestamp_fields(epoch_seconds):
    seconds = int(epoch_seconds)
    ts_inner = encode_varint((1 << 3) | 0) + encode_varint(seconds)
    return (
        encode_length_delimited(3, ts_inner)
        + encode_length_delimited(7, ts_inner)
        + encode_length_delimited(10, ts_inner)
    )

def has_timestamp_fields(inner_blob):
    if not inner_blob:
        return False
    try:
        pos = 0
        while pos < len(inner_blob):
            tag, pos = decode_varint(inner_blob, pos)
            fn = tag >> 3
            wt = tag & 7
            if fn in (3, 7, 10):
                return True
            pos = skip_protobuf_field(inner_blob, pos, wt)
    except Exception:
        pass
    return False

def _prompt_valid_folder(prompt_text):
    while True:
        raw = input(prompt_text).strip()
        if raw == "":
            return None
        folder = raw.strip('"').strip("'").rstrip("\\/")
        if _is_remote_uri(folder):
            print(f"    + Mapped remote URI: {folder}")
            return folder
        if os.path.isdir(folder):
            print(f"    + Mapped to {folder}")
            return folder
        else:
            print(f"    x Path not found: {folder}")
            print(f"      (Make sure the folder exists. Try again or press Enter to skip)")

def interactive_workspace_assignment(unmapped_entries):
    if not unmapped_entries:
        return {}

    print()
    print("  " + "=" * 58)
    print("  WORKSPACE ASSIGNMENT (optional)")
    print("  " + "=" * 58)
    print(f"  {len(unmapped_entries)} conversation(s) have no workspace.")
    print("  You can assign each to a workspace folder now,")
    print("  or press Enter to skip and leave them unassigned.")
    print()

    assignments = {}
    batch_path = None

    for idx, cid, title in unmapped_entries:
        if batch_path:
            assignments[cid] = batch_path
            print(f"    [{idx:3d}] {title[:45]}  -> {os.path.basename(batch_path)}")
            continue

        print(f"  [{idx:3d}] {title[:55]}")
        while True:
            raw = input("    Workspace path (Enter=skip, 'all'=batch, 'q'=stop): ").strip()
            if raw == "":
                print("    Skipped.")
                break
            if raw.lower() == "q":
                print("    Stopped — remaining conversations left unmapped.")
                return assignments
            if raw.lower() == "all":
                folder = _prompt_valid_folder("    Path for ALL remaining (Enter=cancel): ")
                if folder is None:
                    continue
                batch_path = folder
                assignments[cid] = folder
                break
            folder = raw.strip('"').strip("'").rstrip("\\/")
            if _is_remote_uri(folder):
                print(f"    + Mapped remote URI: {folder}")
                assignments[cid] = folder
                break
            if os.path.isdir(folder):
                print(f"    + Mapped to {folder}")
                assignments[cid] = folder
                break
            else:
                print(f"    x Path not found: {folder}")
                print(f"      (Try again or press Enter to skip)")

    if assignments:
        print()
        print(f"  + Assigned workspace to {len(assignments)} conversation(s)")
    print()
    return assignments

def extract_existing_metadata(db_path):
    titles = {}
    inner_blobs = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM ItemTable "
            "WHERE key='antigravityUnifiedStateSync.trajectorySummaries'"
        )
        row = cur.fetchone()
        conn.close()

        if not row or not row[0]:
            return titles, inner_blobs

        decoded = base64.b64decode(row[0])
        pos = 0

        while pos < len(decoded):
            tag, pos = decode_varint(decoded, pos)
            wire_type = tag & 7

            if wire_type != 2:
                break

            length, pos = decode_varint(decoded, pos)
            entry = decoded[pos:pos + length]
            pos += length

            ep, uid, info_b64 = 0, None, None
            while ep < len(entry):
                t, ep = decode_varint(entry, ep)
                fn, wt = t >> 3, t & 7
                if wt == 2:
                    l, ep = decode_varint(entry, ep)
                    content = entry[ep:ep + l]
                    ep += l
                    if fn == 1:
                        uid = content.decode('utf-8', errors='replace')
                    elif fn == 2:
                        sp = 0
                        _, sp = decode_varint(content, sp)
                        sl, sp = decode_varint(content, sp)
                        info_b64 = content[sp:sp + sl].decode('utf-8', errors='replace')
                elif wt == 0:
                    _, ep = decode_varint(entry, ep)
                else:
                    break

            if uid and info_b64:
                try:
                    raw_inner = base64.b64decode(info_b64)
                    inner_blobs[uid] = raw_inner

                    ip = 0
                    _, ip = decode_varint(raw_inner, ip)
                    il, ip = decode_varint(raw_inner, ip)
                    title = raw_inner[ip:ip + il].decode('utf-8', errors='replace')
                    if not title.startswith("Conversation (") and not title.startswith("Conversation "):
                        titles[uid] = title
                except Exception:
                    pass

    except Exception:
        pass

    return titles, inner_blobs

def get_title_from_brain(conversation_id):
    brain_path = os.path.join(BRAIN_DIR, conversation_id)
    if not os.path.isdir(brain_path):
        return None

    for item in sorted(os.listdir(brain_path)):
        if item.startswith('.') or not item.endswith('.md'):
            continue
        try:
            filepath = os.path.join(brain_path, item)
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                first_line = f.readline().strip()
            if first_line.startswith('#'):
                return first_line.lstrip('# ').strip()[:80]
        except Exception:
            pass

    return None

def resolve_title(conversation_id, existing_titles):
    if conversation_id in existing_titles:
        return existing_titles[conversation_id], "preserved"

    brain_title = get_title_from_brain(conversation_id)
    if brain_title:
        return brain_title, "brain"

    conv_file = os.path.join(CONVERSATIONS_DIR, f"{conversation_id}.pb")
    if os.path.exists(conv_file):
        mod_time = time.strftime("%b %d", time.localtime(os.path.getmtime(conv_file)))
        return f"Conversation ({mod_time}) {conversation_id[:8]}", "fallback"

    return f"Conversation {conversation_id[:8]}", "fallback"

def build_trajectory_entry(conversation_id, title, existing_inner_data=None,
                           workspace_path=None, pb_mtime=None):
    if existing_inner_data:
        preserved_fields = strip_field_from_protobuf(existing_inner_data, 1)
        inner_info = encode_string_field(1, title) + preserved_fields
        if workspace_path:
            inner_info = strip_field_from_protobuf(inner_info, 9)
            inner_info += build_workspace_field(workspace_path)
        if pb_mtime and not has_timestamp_fields(existing_inner_data):
            inner_info += build_timestamp_fields(pb_mtime)
    else:
        inner_info = encode_string_field(1, title)
        if workspace_path:
            inner_info += build_workspace_field(workspace_path)
        if pb_mtime:
            inner_info += build_timestamp_fields(pb_mtime)

    info_b64 = base64.b64encode(inner_info).decode('utf-8')
    sub_message = encode_string_field(1, info_b64)

    entry = encode_string_field(1, conversation_id)
    entry += encode_length_delimited(2, sub_message)
    return entry

def main():
    print()
    print("=" * 62)
    print("   Antigravity Conversation Fix  v1.05")
    print("   Rebuilds your conversation index — sorted by date")
    print("=" * 62)
    print()

    if _SYSTEM == "Windows":
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq antigravity.exe'],
                capture_output=True, text=True, creationflags=0x08000000
            )
            if 'antigravity.exe' in result.stdout.lower():
                print("  WARNING: Antigravity is still running!")
                print()
                print("  The fix will NOT work correctly while Antigravity is open.")
                print("  Please close it first: File > Exit, or kill from Task Manager.")
                print()
                choice = input("  Close Antigravity and press Enter to continue (or type Q to quit): ")
                if choice.strip().lower() == 'q':
                    return 1
                print()
        except Exception:
            pass

    if not os.path.exists(DB_PATH):
        print(f"  ERROR: Database not found at:")
        print(f"    {DB_PATH}")
        print()
        print("  Make sure Antigravity has been installed and opened at least once.")
        input("\n  Press Enter to close...")
        return 1

    if not os.path.isdir(CONVERSATIONS_DIR):
        print(f"  ERROR: Conversations directory not found at:")
        print(f"    {CONVERSATIONS_DIR}")
        input("\n  Press Enter to close...")
        return 1

    conv_files = [f for f in os.listdir(CONVERSATIONS_DIR) if f.endswith('.pb')]

    if not conv_files:
        print("  No conversations found on disk. Nothing to fix.")
        input("\n  Press Enter to close...")
        return 0

    conv_files.sort(
        key=lambda f: os.path.getmtime(os.path.join(CONVERSATIONS_DIR, f)),
        reverse=True
    )
    conversation_ids = [f[:-3] for f in conv_files]

    print(f"  Found {len(conversation_ids)} conversations on disk")
    print()

    print("  Reading existing metadata from database...")
    existing_titles, existing_inner_blobs = extract_existing_metadata(DB_PATH)
    ws_count = sum(1 for v in existing_inner_blobs.values()
                   if extract_workspace_hint(v))
    print(f"  Found {len(existing_titles)} existing titles to preserve")
    print(f"  Found {ws_count} conversations with workspace metadata")
    print()

    print("  Scanning conversations (newest first):")
    print("  " + "-" * 58)

    resolved = []  
    stats = {"brain": 0, "preserved": 0, "fallback": 0}
    markers = {"brain": "+", "preserved": "~", "fallback": "?"}

    for i, cid in enumerate(conversation_ids, 1):
        title, source = resolve_title(cid, existing_titles)
        inner_data = existing_inner_blobs.get(cid)
        has_ws = bool(inner_data and extract_workspace_hint(inner_data))
        resolved.append((cid, title, source, inner_data, has_ws))
        stats[source] += 1
        marker = markers[source]
        ws_flag = " [WS]" if has_ws else ""
        print(f"    [{i:3d}] {marker} {title[:50]}{ws_flag}")

    print("  " + "-" * 58)
    print(f"  Legend: [+] brain  [~] preserved  [?] fallback  [WS] workspace")
    print(f"  Totals: {stats['brain']} brain, {stats['preserved']} preserved, {stats['fallback']} fallback")
    print()

    unmapped = [(i, cid, title)
                for i, (cid, title, _, inner_data, has_ws) in enumerate(resolved, 1)
                if not has_ws]

    ws_assignments = {}  

    known_ws_uris = load_known_workspace_uris()
    if known_ws_uris:
        print(f"  Loaded {len(known_ws_uris)} known workspace(s) from workspaceStorage")
    else:
        print("  No workspaceStorage found — using fallback heuristic")
    print()

    if unmapped:
        print(f"  {len(unmapped)} conversation(s) have no workspace assigned.")
        print()
        print("  Press Enter or 1: Auto-assign workspaces (recommended)")
        print("  Press 2:          Auto-assign + manually assign the rest")
        print()
        choice = input("  Your choice: ").strip()

        if os.path.isdir(BRAIN_DIR):
            print()
            print("  Auto-assigning workspaces from brain artifacts...")
            auto_count = 0
            for idx, cid, title in unmapped:
                inferred = infer_workspace_from_brain(cid, known_ws_uris)
                if inferred and (_is_remote_uri(inferred) or os.path.isdir(inferred)):
                    ws_assignments[cid] = inferred
                    auto_count += 1
                    display = os.path.basename(inferred) if not _is_remote_uri(inferred) else inferred
                    print(f"    [{idx:3d}] -> {display}")
            if auto_count:
                print(f"  Auto-assigned {auto_count} workspace(s)")
            else:
                print("  No workspaces could be auto-detected.")
            print()

        if choice == '2':
            still_unmapped = [(idx, cid, title)
                              for idx, cid, title in unmapped
                              if cid not in ws_assignments]
            if still_unmapped:
                user_assignments = interactive_workspace_assignment(still_unmapped)
                ws_assignments.update(user_assignments)
            else:
                print("  All conversations were auto-assigned — nothing left to assign manually.")
                print()

    print("  Building final index...")
    result_bytes = b""
    ws_total = 0
    ts_injected = 0

    for cid, title, source, inner_data, has_ws in resolved:
        ws_path = ws_assignments.get(cid)
        pb_path = os.path.join(CONVERSATIONS_DIR, f"{cid}.pb")
        pb_mtime = os.path.getmtime(pb_path) if os.path.exists(pb_path) else None

        entry = build_trajectory_entry(cid, title, inner_data, ws_path, pb_mtime)
        result_bytes += encode_length_delimited(1, entry)

        if has_ws or ws_path:
            ws_total += 1
        if pb_mtime and (not inner_data or not has_timestamp_fields(inner_data)):
            ts_injected += 1

    print(f"  Workspace: {ws_total} mapped  |  Timestamps injected: {ts_injected}")
    print()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT value FROM ItemTable "
        "WHERE key='antigravityUnifiedStateSync.trajectorySummaries'"
    )
    row = cur.fetchone()

    backup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), BACKUP_FILENAME)
    if row and row[0]:
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(row[0])
        print(f"  Backup saved to: {BACKUP_FILENAME}")

    encoded = base64.b64encode(result_bytes).decode('utf-8')

    if row:
        cur.execute(
            "UPDATE ItemTable SET value=? "
            "WHERE key='antigravityUnifiedStateSync.trajectorySummaries'",
            (encoded,)
        )
    else:
        cur.execute(
            "INSERT INTO ItemTable (key, value) "
            "VALUES ('antigravityUnifiedStateSync.trajectorySummaries', ?)",
            (encoded,)
        )

    conn.commit()
    conn.close()

    total = len(conversation_ids)
    print()
    print("  " + "=" * 58)
    print(f"  SUCCESS! Rebuilt index with {total} conversations.")
    print("  " + "=" * 58)
    print()
    print("  NEXT STEPS:")
    print("    1. Make sure Antigravity is fully closed")
    print("    2. REBOOT your PC (full restart, not just app restart)")
    print("    3. Open Antigravity — conversations should appear sorted by date")
    print()
    input("  Press Enter to close...")
    return 0

if __name__ == "__main__":
    sys.exit(main())