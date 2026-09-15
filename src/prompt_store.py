import hashlib
from typing import Any

from src import db

ASSISTANTS = ("protocol_summary", "safety_narrative")
VARIANTS = ("approved", "proposed")
SHARED_CLAUSE_NAME = "writer-guidance"


def _validate(assistant: str, variant: str | None = None) -> None:
    if assistant not in ASSISTANTS:
        raise ValueError(f"unknown assistant: {assistant}")
    if variant is not None and variant not in VARIANTS:
        raise ValueError(f"unknown prompt variant: {variant}")


def _identity(assistant: str, variant: str, text: str) -> str:
    payload = f"{assistant}\0{variant}\0{text}".encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _store_version(assistant: str, variant: str, text: str) -> str:
    identity = _identity(assistant, variant, text)
    db.execute(
        """
        INSERT INTO prompt_versions (identity, assistant, variant, full_text)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (identity) DO NOTHING
        """,
        (identity, assistant, variant, text),
    )
    db.execute(
        """
        INSERT INTO prompt_history (assistant, variant, prompt_identity)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (assistant, variant, identity),
    )
    return identity


def initialize_store() -> None:
    """Archive current rows and establish immutable identities.

    This is intentionally safe to run repeatedly and also migrates databases
    created by the original starter implementation.
    """
    db.ensure_schema()
    rows = db.fetch_all(
        "SELECT assistant, variant, full_text, prompt_identity FROM prompts"
    )
    for row in rows:
        identity = _store_version(
            row["assistant"], row["variant"], row["full_text"]
        )
        if row["prompt_identity"] != identity:
            db.execute(
                """
                UPDATE prompts SET prompt_identity = %s
                WHERE assistant = %s AND variant = %s
                """,
                (identity, row["assistant"], row["variant"]),
            )


def get_prompt(assistant: str, variant: str = "proposed") -> dict[str, Any]:
    _validate(assistant, variant)
    initialize_store()
    row = db.fetch_one(
        """
        SELECT assistant, variant, full_text, prompt_identity, updated_at
        FROM prompts
        WHERE assistant = %s AND variant = %s
        """,
        (assistant, variant),
    )
    if row is None:
        raise LookupError(f"prompt not found: {assistant}/{variant}")
    if not row["prompt_identity"]:
        raise RuntimeError(f"prompt has no immutable identity: {assistant}/{variant}")
    return {
        "assistant": row["assistant"],
        "variant": row["variant"],
        "text": row["full_text"],
        "identity": row["prompt_identity"],
        "updated_at": row["updated_at"].isoformat(),
    }


def get_prompt_by_identity(identity: str) -> dict[str, Any]:
    initialize_store()
    row = db.fetch_one(
        """
        SELECT identity, assistant, variant, full_text, created_at
        FROM prompt_versions WHERE identity = %s
        """,
        (identity,),
    )
    if row is None:
        raise LookupError(f"prompt identity not found: {identity}")
    return {
        "identity": row["identity"],
        "assistant": row["assistant"],
        "variant": row["variant"],
        "text": row["full_text"],
        "created_at": row["created_at"].isoformat(),
    }


def update_prompt(assistant: str, variant: str, text: str) -> dict[str, Any]:
    _validate(assistant, variant)
    if not text.strip():
        raise ValueError("prompt text must not be empty")
    initialize_store()
    identity = _store_version(assistant, variant, text)
    row = db.execute(
        """
        UPDATE prompts
        SET full_text = %s, prompt_identity = %s, updated_at = now()
        WHERE assistant = %s AND variant = %s
        RETURNING assistant
        """,
        (text, identity, assistant, variant),
    )
    if row is None:
        raise LookupError(f"prompt not found: {assistant}/{variant}")
    return get_prompt(assistant, variant)


def _instruction_body(full_text: str) -> str:
    parts = full_text.split("\n\n", 1)
    return parts[1].strip() if len(parts) == 2 else full_text.strip()


def update_shared(text: str) -> str:
    """Apply one shared wording clause to every assistant and variant.

    Each resulting full prompt receives a new immutable identity; previous
    identities and exact text remain in prompt_versions.
    """
    if not text.strip():
        raise ValueError("shared wording must not be empty")
    initialize_store()
    row = db.execute(
        """
        UPDATE shared_clauses SET clause_text = %s, updated_at = now()
        WHERE name = %s RETURNING name
        """,
        (text.strip(), SHARED_CLAUSE_NAME),
    )
    if row is None:
        raise LookupError(f"shared clause not found: {SHARED_CLAUSE_NAME}")

    current = db.fetch_all(
        "SELECT assistant, variant, full_text FROM prompts ORDER BY assistant, variant"
    )
    for prompt in current:
        combined = f"{text.strip()}\n\n{_instruction_body(prompt['full_text'])}"
        update_prompt(prompt["assistant"], prompt["variant"], combined)
    return text.strip()


def restore_prompt(assistant: str, identity: str) -> dict[str, Any]:
    _validate(assistant)
    historical = get_prompt_by_identity(identity)
    if historical["assistant"] != assistant:
        raise ValueError(
            f"prompt identity {identity} belongs to {historical['assistant']}, not {assistant}"
        )
    variant = historical["variant"]
    row = db.execute(
        """
        UPDATE prompts
        SET full_text = %s, prompt_identity = %s, updated_at = now()
        WHERE assistant = %s AND variant = %s
        RETURNING assistant
        """,
        (historical["text"], identity, assistant, variant),
    )
    if row is None:
        raise LookupError(f"prompt binding not found: {assistant}/{variant}")
    restored = get_prompt(assistant, variant)
    if restored["identity"] != identity or restored["text"] != historical["text"]:
        raise RuntimeError("restored prompt failed identity verification")
    return restored


def list_prompts() -> list[dict]:
    initialize_store()
    return db.fetch_all(
        """
        SELECT assistant, variant, prompt_identity AS identity, updated_at
        FROM prompts ORDER BY assistant, variant
        """
    )
