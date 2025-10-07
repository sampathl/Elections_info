"""Shared CLI helpers for YouTube connector commands."""

from __future__ import annotations

import argparse

from .. import config


def add_auth_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common authentication arguments to a parser."""
    parser.add_argument(
        "--client-secrets",
        default=config.DEFAULT_CLIENT_SECRETS_FILE,
        help="Path to the OAuth client secrets JSON file "
        f"(default: {config.DEFAULT_CLIENT_SECRETS_FILE})",
    )
    parser.add_argument(
        "--token-file",
        default=config.DEFAULT_TOKEN_FILE,
        help="Path to store OAuth tokens "
        f"(default: {config.DEFAULT_TOKEN_FILE})",
    )
