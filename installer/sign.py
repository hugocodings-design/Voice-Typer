"""Update signing (ed25519). Run by publish.ps1; keygen once per publisher.

    venv\\Scripts\\python.exe installer\\sign.py keygen
    venv\\Scripts\\python.exe installer\\sign.py manifest [--required] --setup dist\\VoiceTyperSetup-0.9.0.exe \\
        --notes-fr "…" --notes-en "…" --out dist\\latest.json

The PRIVATE key never goes in the repository: it lives in %USERPROFILE%\\.voice-typer\\ (see
README → "Update signing key"). The public key is written to voice_typer/update_key.py and
ships inside the app, which refuses any update whose latest.json is not signed with it.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from voice_typer import updater  # noqa: E402

KEY_DIR = Path(os.environ.get("VT_SIGNING_DIR", Path.home() / ".voice-typer"))
KEY_FILE = KEY_DIR / "update-signing-key.pem"
PUBLIC_MODULE = ROOT / "voice_typer" / "update_key.py"


def load_private() -> Ed25519PrivateKey:
    if not KEY_FILE.exists():
        raise SystemExit(f"Clé de signature introuvable : {KEY_FILE}\n"
                         "Restaurez-la depuis votre sauvegarde (README → Update signing key).")
    return serialization.load_pem_private_key(KEY_FILE.read_bytes(), password=None)


def public_b64(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def keygen() -> None:
    if KEY_FILE.exists():
        raise SystemExit(f"Une clé existe déjà : {KEY_FILE} (jamais écrasée : les copies installées en dépendent).")
    key = Ed25519PrivateKey.generate()
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    pub = public_b64(key)
    PUBLIC_MODULE.write_text(
        '"""Public key that every update must be signed with (installer/sign.py). Not a secret."""\n\n'
        f'UPDATE_PUBLIC_KEY = "{pub}"\n', encoding="utf-8")
    print(f"Clé privée : {KEY_FILE}\nClé publique : {pub} (écrite dans {PUBLIC_MODULE.name})")
    print("SAUVEGARDEZ la clé privée (clé USB, gestionnaire de mots de passe) : sans elle, "
          "plus aucune mise à jour ne pourra être publiée pour les copies installées.")


def manifest(setup: Path, version: str, notes_fr: str, notes_en: str, out: Path, required: bool = False) -> None:
    key = load_private()
    from voice_typer.update_key import UPDATE_PUBLIC_KEY

    if public_b64(key) != UPDATE_PUBLIC_KEY:
        raise SystemExit("La clé privée ne correspond pas à la clé publique intégrée à l'app : refus de signer.")
    sha = hashlib.sha256()
    with open(setup, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    data = {
        "version": version,
        "url": f"{updater.ALLOWED_PREFIX}v{version}/{setup.name}",
        "sha256": sha.hexdigest(),
        "size": setup.stat().st_size,
        "notes_fr": notes_fr,
        "notes_en": notes_en or notes_fr,
    }
    if required:  # signed like everything else: nobody can make an update "required" without the key
        data["required"] = True
    data["signature"] = base64.b64encode(key.sign(updater.signed_bytes(data))).decode()
    updater.verify_signature(data)  # self-check with the code the app runs
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"latest.json signé : {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen")
    m = sub.add_parser("manifest")
    m.add_argument("--setup", type=Path, required=True)
    m.add_argument("--version", required=True)
    m.add_argument("--notes-fr", default="")
    m.add_argument("--notes-en", default="")
    m.add_argument("--out", type=Path, required=True)
    m.add_argument("--required", action="store_true", help="installed copies install it without asking")
    a = ap.parse_args()
    if a.cmd == "keygen":
        keygen()
    else:
        manifest(a.setup, a.version, a.notes_fr, a.notes_en, a.out, a.required)


if __name__ == "__main__":
    main()
