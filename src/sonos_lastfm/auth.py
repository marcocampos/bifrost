"""Interactive Last.fm authentication helper."""

import getpass
import hashlib
import sys

import pylast


def run_auth() -> None:
    """Interactive auth flow: get API credentials, authenticate, print .env values."""
    print("sonos-lastfm: Last.fm Authentication\n")

    api_key = input("Last.fm API Key: ").strip()
    api_secret = input("Last.fm API Secret: ").strip()

    if not api_key or not api_secret:
        print("Error: API key and secret are required.", file=sys.stderr)
        sys.exit(1)

    username = input("Last.fm Username: ").strip()
    password = getpass.getpass("Last.fm Password: ")

    if not username or not password:
        print("Error: Username and password are required.", file=sys.stderr)
        sys.exit(1)

    password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()

    print("\nAuthenticating with Last.fm...")

    try:
        network = pylast.LastFMNetwork(
            api_key=api_key,
            api_secret=api_secret,
            username=username,
            password_hash=password_hash,
        )
        session_key = network.session_key
    except (pylast.NetworkError, pylast.WSError) as e:
        print(f"Error: Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("Authentication successful!\n")
    print("Add the following to your .env file:\n")
    print(f"LASTFM_API_KEY={api_key}")
    print(f"LASTFM_API_SECRET={api_secret}")
    print(f"LASTFM_USERNAME={username}")
    print(f"LASTFM_PASSWORD_HASH={password_hash}")
    if session_key:
        print(f"LASTFM_SESSION_KEY={session_key}")
