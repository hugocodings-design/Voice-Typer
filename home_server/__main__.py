"""python -m home_server [--port 8765] — see server.py and docs/HOME.md."""

import argparse
import sys

from home_server.server import Models, home_dir, load_or_create_key, make_server


def main() -> None:
    from voice_typer import __version__, portable

    portable.use_private_temp()
    parser = argparse.ArgumentParser(description="Voice Typer Home")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--new-key", action="store_true", help="replace the key (other PCs must be updated)")
    parser.add_argument("--only-key", action="store_true", help="just show the key and stop")
    args = parser.parse_args()

    if args.new_key:
        (home_dir() / "key.txt").unlink(missing_ok=True)
    key = load_or_create_key()
    if args.only_key:
        print(f"Clé{' (nouvelle)' if args.new_key else ''} : {key}")
        print("Mettez-la dans Réglages → PC à la maison sur vos autres ordinateurs, puis redémarrez Voice Typer Home.")
        return
    models = Models()
    server = make_server(models, key, args.port, __version__)
    print("=" * 70)
    print(f" Voice Typer Home {__version__} — en écoute sur ce PC seulement (127.0.0.1:{args.port})")
    print(" Dans Voice Typer au travail, Réglages → PC à la maison :")
    print("   Adresse : celle affichée par  tailscale funnel status")
    print(f"   Clé     : {key}")
    print(" Gardez cette fenêtre ouverte. Ctrl+C pour arrêter.")
    print("=" * 70)
    from home_server.tray_app import load_message

    models.on_event = lambda kind, source, device, error: (
        print(" ! " + msg) if (msg := load_message(kind, source, device, error)) else None)
    models.configure()
    print(f" Modèles de ce PC (utilisés si l'autre PC n'en précise pas) : {models.defaults['whisper']}, "
          f"{models.defaults['writer']}")
    models.preload()   # in the background: answers "loading" until ready
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    sys.exit(0)


if __name__ == "__main__":
    main()
