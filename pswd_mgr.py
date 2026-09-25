#!/usr/bin/env python3

import base64
import json
import os
import sys
import subprocess
import tempfile
import threading
import time
from pathlib import Path

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

import pygame
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


# ============================================================
# CONFIGURATION
# ============================================================

WIDTH, HEIGHT = 1000, 680
FPS = 60
VAULT_FILE = Path.home() / ".jarvis_password_vault.enc"

# Time delay (in seconds) between English and Malayalam voices
VOICE_INTERVAL = 1.8  # Increase or decrease this value to adjust pause length

BG = (5, 10, 18)
PANEL = (10, 20, 32)
CYAN = (80, 230, 255)
ICE = (210, 250, 255)
GREEN = (100, 255, 170)
RED = (255, 95, 110)
YELLOW = (255, 220, 100)
MUTED = (120, 155, 175)
WHITE = (240, 248, 255)

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


# ============================================================
# ENCRYPTION
# ============================================================

def derive_key(master_password, salt):
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P
    )
    key = kdf.derive(master_password.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


def encrypt_vault(data, master_password):
    salt = os.urandom(16)
    key = derive_key(master_password, salt)
    cipher = Fernet(key)

    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    encrypted = cipher.encrypt(plaintext)

    package = {
        "version": 1,
        "salt": base64.b64encode(salt).decode(),
        "data": encrypted.decode()
    }

    return json.dumps(package).encode("utf-8")


def decrypt_vault(raw_data, master_password):
    package = json.loads(raw_data.decode("utf-8"))
    salt = base64.b64decode(package["salt"])
    encrypted = package["data"].encode()

    key = derive_key(master_password, salt)
    cipher = Fernet(key)

    plaintext = cipher.decrypt(encrypted)
    return json.loads(plaintext.decode("utf-8"))


def save_vault(data, master_password):
    encrypted = encrypt_vault(data, master_password)
    temp_file = VAULT_FILE.with_suffix(".tmp")
    temp_file.write_bytes(encrypted)

    try:
        os.chmod(temp_file, 0o600)
    except OSError:
        pass

    temp_file.replace(VAULT_FILE)

    try:
        os.chmod(VAULT_FILE, 0o600)
    except OSError:
        pass


def load_vault(master_password):
    return decrypt_vault(
        VAULT_FILE.read_bytes(),
        master_password
    )


# ============================================================
# VOICE SYNTHESIS (SEQUENTIAL WITH ADJUSTABLE PAUSE)
# ============================================================

_voice_engine = None
_speech_lock = threading.Lock()

TRANSLATIONS = {
    "IRONVAULT IS ACTIVE, ALL SYSTEMS ONLINE": "അയൺവോൾട്ട് സജീവമാണ്, എല്ലാ സിസ്റ്റങ്ങളും ഓൺലൈനിലാണ്",
    "SHUTTING DOWN IRONVAULT": "അയൻവോൾട്ട് ഓഫ് ചെയ്യുന്നു",
    "MASTER PASSWORD CREATED SUCCESSFULLY": "മാസ്റ്റർ പാസ്‌വേഡ് വിജയകരമായി സൃഷ്ടിച്ചു",
    "SUCCESSFULLY LOGGED IN": "വിജയകരമായി ലോഗിൻ ചെയ്തു",
    "INCORRECT MASTER PASSWORD": "തെറ്റായ മാസ്റ്റർ പാസ്‌വേഡ്",
    "Vault reset. Creating new vault.": "വോൾട്ട് റീസെറ്റ് ചെയ്തു. പുതിയ വോൾട്ട് ഉണ്ടാക്കുന്നു.",
    "Incorrect password.": "തെറ്റായ പാസ്‌വേഡ്.",
    "This account already exists.": "ഈ അക്കൗണ്ട് നിലവിലുണ്ട്.",
    "Account created successfully.": "അക്കൗണ്ട് വിജയകരമായി സൃഷ്ടിച്ചു.",
    "Account not found.": "അക്കൗണ്ട് കണ്ടെത്തിയില്ല.",
    "Another account already uses this service and username.": "മറ്റൊരു അക്കൗണ്ട് ഈ സേവനവും ഉപയോക്തൃനാമവും ഉപയോഗിക്കുന്നു.",
    "Account updated successfully.": "അക്കൗണ്ട് വിജയകരമായി പുതുക്കി.",
    "Account found. Password displayed.": "അക്കൗണ്ട് കണ്ടെത്തി. പാസ്‌വേഡ് കാണിക്കുന്നു.",
    "Account deleted successfully.": "അക്കൗണ്ട് വിജയകരമായി നീക്കം ചെയ്തു.",
}


def speak_malayalam_gtts(text):
    """Plays clear Malayalam voice audio using gTTS."""
    if not GTTS_AVAILABLE:
        return False

    try:
        tts = gTTS(text=text, lang='ml', slow=False)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_path = fp.name

        tts.save(temp_path)

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(30)

        pygame.mixer.music.unload()
        try:
            os.remove(temp_path)
        except Exception:
            pass
        return True
    except Exception:
        return False


def speak_text_engine(text, lang="en"):
    global _voice_engine

    if lang == "ml":
        if speak_malayalam_gtts(text):
            return

    try:
        if pyttsx3 is not None:
            if _voice_engine is None:
                _voice_engine = pyttsx3.init()
                _voice_engine.setProperty("rate", 155)
                _voice_engine.setProperty("volume", 1.0)

            voices = _voice_engine.getProperty("voices")
            preferred_voice = None

            if lang == "ml":
                for voice in voices:
                    if "ml" in voice.id.lower() or "malayalam" in voice.name.lower():
                        preferred_voice = voice.id
                        break
            else:
                high_quality_names = ["zira", "samantha", "hazel", "david", "caren", "victoria", "eva"]
                for voice in voices:
                    voice_name = voice.name.lower()
                    if any(name in voice_name for name in high_quality_names):
                        preferred_voice = voice.id
                        break

                if not preferred_voice and voices:
                    for voice in voices:
                        if "en" in voice.id.lower() or "english" in voice.name.lower():
                            preferred_voice = voice.id
                            break

            if preferred_voice:
                _voice_engine.setProperty("voice", preferred_voice)

            _voice_engine.say(text)
            _voice_engine.runAndWait()
            return
    except Exception:
        pass

    voice_flag = "ml" if lang == "ml" else "en-us+f3"
    try:
        subprocess.run(
            ["espeak-ng", "-s", "140", "-v", voice_flag, text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        try:
            subprocess.run(
                ["espeak", "-s", "140", "-v", voice_flag, text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass


def speak(text_en, text_ml=None):
    """Enforces strict sequential voice output with an increased interval between English and Malayalam."""
    with _speech_lock:
        # 1. Speak English fully
        speak_text_engine(text_en, lang="en")

        # 2. Pause between English and Malayalam (controlled by VOICE_INTERVAL)
        time.sleep(VOICE_INTERVAL)

        # 3. Determine Malayalam translation
        if text_ml is None:
            text_ml = TRANSLATIONS.get(text_en)

        # 4. Speak Malayalam after the pause
        if text_ml:
            speak_text_engine(text_ml, lang="ml")
            time.sleep(0.3)


# ============================================================
# PYGAME ENGINE
# ============================================================

pygame.init()
if not pygame.mixer.get_init():
    pygame.mixer.init()

fullscreen = False
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("IRONVAULT // PASSWORD MANAGER")


def toggle_fullscreen():
    global screen, fullscreen
    fullscreen = not fullscreen

    if fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)


clock = pygame.time.Clock()

FONT = pygame.font.SysFont("DejaVu Sans", 23)
SMALL = pygame.font.SysFont("DejaVu Sans", 18)
BIG = pygame.font.SysFont("DejaVu Sans", 34, bold=True)
TITLE = pygame.font.SysFont("DejaVu Sans", 42, bold=True)


def draw_text(text, x, y, font=FONT, color=WHITE, center=False):
    surface = font.render(text, True, color)
    if center:
        rect = surface.get_rect(center=(x, y))
    else:
        rect = surface.get_rect(topleft=(x, y))
    screen.blit(surface, rect)


def header(title="ALL SYSTEMS ONLINE"):
    screen.fill(BG)
    pygame.draw.rect(screen, PANEL, (0, 0, WIDTH, 85))
    pygame.draw.line(screen, CYAN, (25, 83), (WIDTH - 25, 83), 2)
    
    draw_text("IRONVAULT", 35, 8, TITLE, CYAN)
    draw_text("IRONVAULT PASSWORD MANAGER", 35, 54, SMALL, MUTED)
    
    draw_text(title, WIDTH - 35, 31, SMALL, MUTED)


# ============================================================
# INPUT & NOTIFICATIONS
# ============================================================

def text_input(prompt, hidden=False):
    value = ""
    pygame.key.start_text_input()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.key.stop_text_input()
                speak("SHUTTING DOWN IRONVAULT")
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    pygame.key.stop_text_input()
                    return value, True

                if event.key == pygame.K_ESCAPE:
                    pygame.key.stop_text_input()
                    return "", False

                if event.key == pygame.K_BACKSPACE:
                    value = value[:-1]

            elif event.type == pygame.TEXTINPUT:
                if len(value) < 200:
                    value += event.text

        header("INPUT REQUIRED")
        draw_text(prompt, 60, 140, BIG, ICE)

        pygame.draw.rect(screen, (18, 32, 48), (60, 210, WIDTH - 120, 70), border_radius=10)
        pygame.draw.rect(screen, CYAN, (60, 210, WIDTH - 120, 70), width=2, border_radius=10)

        shown = "•" * len(value) if hidden else value
        draw_text(shown, 80, 232, FONT, WHITE)
        draw_text("ENTER = Confirm     ESC = Cancel", 60, 305, SMALL, MUTED)

        pygame.display.flip()
        clock.tick(FPS)


def message(text, color=ICE):
    screen.fill(BG)
    pygame.draw.rect(screen, PANEL, (70, 210, WIDTH - 140, 220), border_radius=15)
    pygame.draw.rect(screen, color, (70, 210, WIDTH - 140, 220), width=2, border_radius=15)

    lines = text.split("\n")
    for i, line in enumerate(lines):
        draw_text(line, WIDTH // 2, 270 + i * 40, FONT, color, center=True)

    draw_text("Press ENTER to continue", WIDTH // 2, 390, SMALL, MUTED, center=True)
    pygame.display.flip()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                speak("SHUTTING DOWN IRONVAULT")
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                    return
        clock.tick(FPS)


# ============================================================
# MASTER PASSWORD SETUP & UNLOCK
# ============================================================

def create_master_password():
    while True:
        password, ok = text_input("Create new master password:", hidden=True)
        if not ok:
            return None

        if len(password) < 8:
            message("Master password must contain\nat least 8 characters.", RED)
            continue

        confirm, ok = text_input("Confirm master password:", hidden=True)
        if not ok:
            return None

        if password != confirm:
            message("Passwords do not match.", RED)
            continue

        return password


def unlock_vault():
    if not VAULT_FILE.exists():
        message("No vault found on this device.\nCreate your master password.", CYAN)
        master = create_master_password()
        if master is None:
            return None, None

        data = {"version": 1, "entries": []}
        save_vault(data, master)
        message("MASTER PASSWORD CREATED SUCCESSFULLY", GREEN)
        speak("MASTER PASSWORD CREATED SUCCESSFULLY")
        return data, master

    while True:
        master, ok = text_input("Enter master password:", hidden=True)
        if not ok:
            return None, None

        try:
            data = load_vault(master)
            speak("SUCCESSFULLY LOGGED IN")
            return data, master
        except (InvalidToken, KeyError, ValueError):
            speak("INCORRECT MASTER PASSWORD")
            screen.fill(BG)
            pygame.draw.rect(screen, PANEL, (70, 200, WIDTH - 140, 240), border_radius=15)
            pygame.draw.rect(screen, RED, (70, 200, WIDTH - 140, 240), width=2, border_radius=15)

            draw_text("INCORRECT MASTER PASSWORD", WIDTH // 2, 240, FONT, RED, center=True)
            draw_text("Press [ENTER] to try again", WIDTH // 2, 300, SMALL, ICE, center=True)
            draw_text("Press [R] to wipe and RESET VAULT", WIDTH // 2, 340, SMALL, YELLOW, center=True)
            pygame.display.flip()

            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    if event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                            waiting = False
                        elif event.key == pygame.K_r:
                            if VAULT_FILE.exists():
                                VAULT_FILE.unlink()
                            speak("Vault reset. Creating new vault.")
                            message("Vault reset. Creating new vault...", YELLOW)
                            return unlock_vault()
                clock.tick(FPS)


def edit_master_password(data, current_master):
    verify, ok = text_input("Enter current master password:", hidden=True)
    if not ok:
        return current_master

    if verify != current_master:
        message("Incorrect master password.", RED)
        speak("Incorrect password.")
        return current_master

    new_master = create_master_password()
    if new_master is None:
        return current_master

    if new_master == current_master:
        message("New password must be different.", YELLOW)
        return current_master

    save_vault(data, new_master)
    message("MASTER PASSWORD CREATED SUCCESSFULLY", GREEN)
    speak("MASTER PASSWORD CREATED SUCCESSFULLY")
    return new_master


# ============================================================
# ACCOUNT OPERATIONS
# ============================================================

def add_account(data, master):
    service, ok = text_input("Service name (e.g., Instagram):")
    if not ok:
        return

    username, ok = text_input("Username / Email:")
    if not ok:
        return

    service_clean = service.strip()
    username_clean = username.strip()

    for account in data["entries"]:
        if (
            account["service"].strip().lower() == service_clean.lower()
            and account["username"].strip().lower() == username_clean.lower()
        ):
            message("This account already exists.\nUse EDIT ACCOUNT to change it.", YELLOW)
            speak("This account already exists.")
            return

    password, ok = text_input("Password:", hidden=True)
    if not ok:
        return

    notes, ok = text_input("Notes (optional):")
    if not ok:
        return

    entry = {
        "service": service_clean,
        "username": username_clean,
        "password": password,
        "notes": notes.strip()
    }

    data["entries"].append(entry)
    save_vault(data, master)
    message("Account created successfully.", GREEN)
    speak("Account created successfully.")
    speak(
        f"Service: {service_clean}, Username: {username_clean}",
        f"സർവീസ്: {service_clean}, യൂസർനെയിം: {username_clean}"
    )


def edit_account(data, master):
    service, ok = text_input("Service of account to edit:")
    if not ok:
        return

    username, ok = text_input("Username of account to edit:")
    if not ok:
        return

    service = service.strip().lower()
    username = username.strip().lower()

    matches = [
        acc for acc in data["entries"]
        if acc["service"].strip().lower() == service and acc["username"].strip().lower() == username
    ]

    if not matches:
        message("Account not found.", YELLOW)
        speak("Account not found.")
        return

    account = matches[0]

    new_service, ok = text_input(f"Service [{account['service']}] - new value:")
    if not ok:
        return

    new_username, ok = text_input(f"Username [{account['username']}] - new value:")
    if not ok:
        return

    new_password, ok = text_input("New password (leave blank to keep current):", hidden=True)
    if not ok:
        return

    new_notes, ok = text_input(f"Notes [{account['notes']}] - new value:")
    if not ok:
        return

    service_value = new_service.strip() or account["service"]
    username_value = new_username.strip() or account["username"]
    password_value = new_password if new_password else account["password"]
    notes_value = new_notes.strip() or account["notes"]

    for other in data["entries"]:
        if other is account:
            continue
        if (
            other["service"].strip().lower() == service_value.lower()
            and other["username"].strip().lower() == username_value.lower()
        ):
            message("Another account already uses this\nservice and username.", RED)
            speak("Another account already uses this service and username.")
            return

    account["service"] = service_value
    account["username"] = username_value
    account["password"] = password_value
    account["notes"] = notes_value

    save_vault(data, master)
    message("Account updated successfully.", GREEN)
    speak("Account updated successfully.")
    speak(
        f"Service: {service_value}, Username: {username_value}",
        f"സർവീസ്: {service_value}, യൂസർനേയിം: {username_value}"
    )


def find_password(data):
    service, ok = text_input("Service:")
    if not ok:
        return

    username, ok = text_input("Username:")
    if not ok:
        return

    service = service.strip().lower()
    username = username.strip().lower()

    results = [
        acc for acc in data["entries"]
        if acc["service"].lower() == service and acc["username"].lower() == username
    ]

    if not results:
        message("No matching account found.", YELLOW)
        speak("Account not found.")
        return

    account = results[0]

    screen.fill(BG)
    pygame.draw.rect(screen, PANEL, (45, 100, WIDTH - 90, 470), border_radius=16)
    pygame.draw.rect(screen, GREEN, (45, 100, WIDTH - 90, 470), width=2, border_radius=16)

    draw_text("ACCOUNT FOUND", WIDTH // 2, 145, BIG, GREEN, center=True)
    speak("Account found. Password displayed.")

    draw_text(f"Service  : {account['service']}", 90, 215, FONT, ICE)
    draw_text(f"Username : {account['username']}", 90, 265, FONT, ICE)
    draw_text(f"Password : {account['password']}", 90, 315, FONT, YELLOW)

    if account["notes"]:
        draw_text(f"Notes    : {account['notes']}", 90, 370, SMALL, MUTED)

    draw_text("Press ENTER to return", WIDTH // 2, 500, SMALL, MUTED, center=True)
    pygame.display.flip()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                speak("SHUTTING DOWN IRONVAULT")
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    return
        clock.tick(FPS)


def list_accounts(data):
    header("SAVED ACCOUNTS")
    entries = data["entries"]

    if not entries:
        draw_text("No accounts saved.", WIDTH // 2, 200, BIG, YELLOW, center=True)
    else:
        y = 125
        for number, account in enumerate(entries, 1):
            draw_text(
                f"{number}. {account['service']}  →  {account['username']}",
                70, y, FONT, ICE
            )
            y += 45
            if y > HEIGHT - 90:
                break

    draw_text("Press ENTER to return", WIDTH // 2, HEIGHT - 40, SMALL, MUTED, center=True)
    pygame.display.flip()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                speak("SHUTTING DOWN IRONVAULT")
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    return
        clock.tick(FPS)


def delete_account(data, master):
    service, ok = text_input("Service:")
    if not ok:
        return

    username, ok = text_input("Username:")
    if not ok:
        return

    service_clean = service.strip()
    username_clean = username.strip()

    original_count = len(data["entries"])
    data["entries"] = [
        acc for acc in data["entries"]
        if not (acc["service"].strip().lower() == service_clean.lower() and acc["username"].strip().lower() == username_clean.lower())
    ]

    if len(data["entries"]) == original_count:
        message("Account not found.", YELLOW)
        speak("Account not found.")
        return

    save_vault(data, master)
    message("Account deleted.", GREEN)
    speak("Account deleted successfully.")
    speak(
        f"Service: {service_clean}, Username: {username_clean}",
        f"സർവീസ്: {service_clean}, യൂസർനേയിം: {username_clean}"
    )


# ============================================================
# MAIN MENU
# ============================================================

def main_menu(data, master):
    while True:
        header("ALL SYSTEMS ONLINE")
        draw_text("IRONVAULT", WIDTH // 2, 105, TITLE, CYAN, center=True)
        draw_text("IRONVAULT PASSWORD MANAGER", WIDTH // 2, 148, SMALL, MUTED, center=True)

        options = [
            ("A", "Add account"),
            ("E", "Edit account"),
            ("F", "Find / reveal password"),
            ("L", "List accounts"),
            ("D", "Delete account"),
            ("M", "Change master password"),
            ("Q", "Lock and exit")
        ]

        y = 185
        for key, label in options:
            pygame.draw.rect(screen, PANEL, (200, y - 7, 600, 48), border_radius=9)
            draw_text(f"[{key}]", 225, y, FONT, CYAN)
            draw_text(label, 315, y, FONT, WHITE)
            y += 62

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                speak("SHUTTING DOWN IRONVAULT")
                pygame.quit()
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    toggle_fullscreen()
                    continue

                key = event.unicode.lower()

                if key == "a":
                    add_account(data, master)
                elif key == "e":
                    edit_account(data, master)
                elif key == "f":
                    find_password(data)
                elif key == "l":
                    list_accounts(data)
                elif key == "d":
                    delete_account(data, master)
                elif key == "m":
                    master = edit_master_password(data, master)
                elif key == "q" or event.key == pygame.K_ESCAPE:
                    speak("SHUTTING DOWN IRONVAULT")
                    pygame.quit()
                    return

        clock.tick(FPS)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    threading.Thread(
        target=speak,
        args=("IRONVAULT IS ACTIVE, ALL SYSTEMS ONLINE",),
        daemon=True
    ).start()

    data, master = unlock_vault()
    if data is None:
        pygame.quit()
        return
    main_menu(data, master)


if __name__ == "__main__":
    main()