#!/usr/bin/env python3

import base64
import json
import os
import sys
import subprocess
from pathlib import Path

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

import pygame
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


# ============================================================
# CONFIGURATION
# ============================================================

WIDTH, HEIGHT = 1000, 680
FPS = 60
VAULT_FILE = Path.home() / ".jarvis_password_vault.enc"

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
# VOICE SYNTHESIS
# ============================================================

_voice_engine = None

def speak(text):
    global _voice_engine

    try:
        if pyttsx3 is not None:
            if _voice_engine is None:
                _voice_engine = pyttsx3.init()
                _voice_engine.setProperty("rate", 165)
                _voice_engine.setProperty("volume", 1.0)

            _voice_engine.say(text)
            _voice_engine.runAndWait()
            return
    except Exception:
        pass

    try:
        subprocess.run(
            ["espeak", "-s", "165", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


# ============================================================
# PYGAME ENGINE
# ============================================================

pygame.init()

fullscreen = False
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("J.A.R.V.I.S. // SECURE PASSWORD VAULT")


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


def header(title="SECURE PASSWORD VAULT"):
    screen.fill(BG)
    pygame.draw.rect(screen, PANEL, (0, 0, WIDTH, 82))
    pygame.draw.line(screen, CYAN, (25, 80), (WIDTH - 25, 80), 2)
    draw_text("J.A.R.V.I.S.", 35, 18, TITLE, CYAN)
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
    # First run: prompt user to set up initial master password
    if not VAULT_FILE.exists():
        message("No vault found on this device.\nCreate your master password.", CYAN)
        master = create_master_password()
        if master is None:
            return None, None

        data = {"version": 1, "entries": []}
        save_vault(data, master)
        message("Secure vault created successfully.", GREEN)
        speak("Secure vault created successfully.")
        return data, master

    # Existing vault login
    while True:
        master, ok = text_input("Enter master password:", hidden=True)
        if not ok:
            return None, None

        try:
            data = load_vault(master)
            return data, master
        except (InvalidToken, KeyError, ValueError):
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
    message("Master password updated successfully.", GREEN)
    speak("Master password updated successfully.")
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

    service = service.strip().lower()
    username = username.strip().lower()

    original_count = len(data["entries"])
    data["entries"] = [
        acc for acc in data["entries"]
        if not (acc["service"].lower() == service and acc["username"].lower() == username)
    ]

    if len(data["entries"]) == original_count:
        message("Account not found.", YELLOW)
        speak("Account not found.")
        return

    save_vault(data, master)
    message("Account deleted.", GREEN)
    speak("Account deleted successfully.")


# ============================================================
# MAIN MENU
# ============================================================

def main_menu(data, master):
    while True:
        header("ALL SYSTEMS ONLINE")
        draw_text("SECURE PASSWORD VAULT", WIDTH // 2, 125, BIG, CYAN, center=True)

        options = [
            ("A", "Add account"),
            ("E", "Edit account"),
            ("F", "Find / reveal password"),
            ("L", "List accounts"),
            ("D", "Delete account"),
            ("M", "Change master password"),
            ("Q", "Lock and exit")
        ]

        y = 175
        for key, label in options:
            pygame.draw.rect(screen, PANEL, (200, y - 7, 600, 48), border_radius=9)
            draw_text(f"[{key}]", 225, y, FONT, CYAN)
            draw_text(label, 315, y, FONT, WHITE)
            y += 62

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
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
                    pygame.quit()
                    return

        clock.tick(FPS)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    data, master = unlock_vault()
    if data is None:
        pygame.quit()
        return
    main_menu(data, master)


if __name__ == "__main__":
    main()