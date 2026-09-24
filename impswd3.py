#!/usr/bin/env python3

import base64
import json
import os
import sys
from pathlib import Path

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

    plaintext = json.dumps(
        data,
        ensure_ascii=False
    ).encode("utf-8")

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
# PYGAME
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

    pygame.draw.rect(
        screen,
        PANEL,
        (0, 0, WIDTH, 82)
    )

    pygame.draw.line(
        screen,
        CYAN,
        (25, 80),
        (WIDTH - 25, 80),
        2
    )

    draw_text(
        "J.A.R.V.I.S.",
        35,
        18,
        TITLE,
        CYAN
    )

    draw_text(
        title,
        WIDTH - 35,
        31,
        SMALL,
        MUTED
    )


# ============================================================
# INPUT
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

        header("INPUT")

        draw_text(
            prompt,
            60,
            140,
            BIG,
            ICE
        )

        pygame.draw.rect(
            screen,
            (18, 32, 48),
            (60, 210, WIDTH - 120, 70),
            border_radius=10
        )

        pygame.draw.rect(
            screen,
            CYAN,
            (60, 210, WIDTH - 120, 70),
            width=2,
            border_radius=10
        )

        shown = "•" * len(value) if hidden else value

        draw_text(
            shown,
            80,
            232,
            FONT,
            WHITE
        )

        draw_text(
            "ENTER = confirm     ESC = cancel",
            60,
            305,
            SMALL,
            MUTED
        )

        pygame.display.flip()
        clock.tick(FPS)


# ============================================================
# MESSAGE
# ============================================================

def message(text, color=ICE):

    screen.fill(BG)

    pygame.draw.rect(
        screen,
        PANEL,
        (70, 210, WIDTH - 140, 220),
        border_radius=15
    )

    pygame.draw.rect(
        screen,
        color,
        (70, 210, WIDTH - 140, 220),
        width=2,
        border_radius=15
    )

    lines = text.split("\n")

    for i, line in enumerate(lines):
        draw_text(
            line,
            WIDTH // 2,
            270 + i * 40,
            FONT,
            color,
            center=True
        )

    draw_text(
        "Press ENTER to continue",
        WIDTH // 2,
        390,
        SMALL,
        MUTED,
        center=True
    )

    pygame.display.flip()

    while True:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key in (
                    pygame.K_RETURN,
                    pygame.K_ESCAPE,
                    pygame.K_SPACE
                ):
                    return

        clock.tick(FPS)


# ============================================================
# MASTER PASSWORD
# ============================================================

def create_master_password():

    while True:

        password, ok = text_input(
            "Create master password:",
            hidden=True
        )

        if not ok:
            return None

        if len(password) < 8:
            message(
                "Master password must contain\n"
                "at least 8 characters.",
                RED
            )
            continue

        confirm, ok = text_input(
            "Confirm master password:",
            hidden=True
        )

        if not ok:
            return None

        if password != confirm:
            message(
                "Passwords do not match.",
                RED
            )
            continue

        return password


def unlock_vault():

    # First run
    if not VAULT_FILE.exists():

        message(
            "No vault found.\n"
            "Create your secure vault.",
            CYAN
        )

        master = create_master_password()

        if master is None:
            return None, None

        data = {
            "version": 1,
            "entries": []
        }

        save_vault(data, master)

        message(
            "Secure vault created successfully.",
            GREEN
        )

        return data, master

    # Existing vault
    while True:

        master, ok = text_input(
            "Enter master password:",
            hidden=True
        )

        if not ok:
            return None, None

        try:

            data = load_vault(master)

            return data, master

        except (InvalidToken, KeyError, ValueError):

            message(
                "Incorrect master password.",
                RED
            )


# ============================================================
# ADD ACCOUNT
# ============================================================

def add_account(data, master):

    service, ok = text_input(
        "Service name (example: Instagram):"
    )

    if not ok:
        return

    username, ok = text_input(
        "Username:"
    )

    if not ok:
        return

    password, ok = text_input(
        "Password:",
        hidden=True
    )

    if not ok:
        return

    notes, ok = text_input(
        "Notes (optional):"
    )

    if not ok:
        return

    entry = {
        "service": service.strip(),
        "username": username.strip(),
        "password": password,
        "notes": notes.strip()
    }

    data["entries"].append(entry)

    save_vault(data, master)

    message(
        "Account saved in encrypted vault.",
        GREEN
    )


# ============================================================
# FIND PASSWORD
# ============================================================

def find_password(data):

    service, ok = text_input(
        "Service:"
    )

    if not ok:
        return

    username, ok = text_input(
        "Username:"
    )

    if not ok:
        return

    service = service.strip().lower()
    username = username.strip().lower()

    results = []

    for account in data["entries"]:

        if (
            account["service"].lower() == service
            and
            account["username"].lower() == username
        ):
            results.append(account)

    if not results:

        message(
            "No matching account found.",
            YELLOW
        )

        return

    account = results[0]

    screen.fill(BG)

    pygame.draw.rect(
        screen,
        PANEL,
        (45, 100, WIDTH - 90, 470),
        border_radius=16
    )

    pygame.draw.rect(
        screen,
        GREEN,
        (45, 100, WIDTH - 90, 470),
        width=2,
        border_radius=16
    )

    draw_text(
        "ACCOUNT FOUND",
        WIDTH // 2,
        145,
        BIG,
        GREEN,
        center=True
    )

    draw_text(
        f"Service  : {account['service']}",
        90,
        215,
        FONT,
        ICE
    )

    draw_text(
        f"Username : {account['username']}",
        90,
        265,
        FONT,
        ICE
    )

    draw_text(
        f"Password : {account['password']}",
        90,
        315,
        FONT,
        YELLOW
    )

    if account["notes"]:
        draw_text(
            f"Notes    : {account['notes']}",
            90,
            370,
            SMALL,
            MUTED
        )

    draw_text(
        "Press ENTER to return",
        WIDTH // 2,
        500,
        SMALL,
        MUTED,
        center=True
    )

    pygame.display.flip()

    while True:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key in (
                    pygame.K_RETURN,
                    pygame.K_ESCAPE
                ):
                    return

        clock.tick(FPS)


# ============================================================
# LIST ACCOUNTS
# ============================================================

def list_accounts(data):

    header("SAVED ACCOUNTS")

    entries = data["entries"]

    if not entries:

        draw_text(
            "No accounts saved.",
            WIDTH // 2,
            200,
            BIG,
            YELLOW,
            center=True
        )

    else:

        y = 125

        for number, account in enumerate(entries, 1):

            draw_text(
                f"{number}. {account['service']}  →  "
                f"{account['username']}",
                70,
                y,
                FONT,
                ICE
            )

            y += 45

            if y > HEIGHT - 90:
                break

    draw_text(
        "Press ENTER to return",
        WIDTH // 2,
        HEIGHT - 40,
        SMALL,
        MUTED,
        center=True
    )

    pygame.display.flip()

    while True:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:

                if event.key in (
                    pygame.K_RETURN,
                    pygame.K_ESCAPE
                ):
                    return

        clock.tick(FPS)


# ============================================================
# DELETE
# ============================================================

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
        account
        for account in data["entries"]
        if not (
            account["service"].lower() == service
            and
            account["username"].lower() == username
        )
    ]

    if len(data["entries"]) == original_count:

        message(
            "Account not found.",
            YELLOW
        )

        return

    save_vault(data, master)

    message(
        "Account deleted.",
        GREEN
    )


# ============================================================
# MAIN MENU
# ============================================================

def main_menu(data, master):

    while True:

        header("ALL SYSTEMS ONLINE")

        draw_text(
            "SECURE PASSWORD VAULT",
            WIDTH // 2,
            125,
            BIG,
            CYAN,
            center=True
        )

        options = [
            ("A", "Add account"),
            ("F", "Find / reveal password"),
            ("L", "List accounts"),
            ("D", "Delete account"),
            ("Q", "Lock and exit")
        ]

        y = 205

        for key, label in options:

            pygame.draw.rect(
                screen,
                PANEL,
                (220, y - 7, 560, 48),
                border_radius=9
            )

            draw_text(
                f"[{key}]",
                250,
                y,
                FONT,
                CYAN
            )

            draw_text(
                label,
                330,
                y,
                FONT,
                WHITE
            )

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

                elif key == "f":
                    find_password(data)

                elif key == "l":
                    list_accounts(data)

                elif key == "d":
                    delete_account(data, master)

                elif key == "q" or event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return

        clock.tick(FPS)


# ============================================================
# START
# ============================================================

def main():

    data, master = unlock_vault()

    if data is None:
        pygame.quit()
        return

    main_menu(data, master)


if __name__ == "__main__":
    main()
