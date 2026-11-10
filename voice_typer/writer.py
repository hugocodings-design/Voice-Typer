"""Local AI rewriting ("post-processing") of a transcript, e.g. into a well-formatted email.

Runs a small instruction-tuned LLM *inside* the app with CTranslate2 — the same engine as
faster-whisper — so there is nothing else to install (no Ollama / LM Studio server).
Models are CTranslate2 int8 conversions of Qwen 2.5 Instruct (strong in French and English).
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from voice_typer import gpu

gpu.setup_dll_paths()

import ctranslate2  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402
from tokenizers import Tokenizer  # noqa: E402


@dataclass(frozen=True)
class LlmInfo:
    source: str
    label: str
    size: str
    note_fr: str
    note_en: str


LLM_CATALOG = [
    LlmInfo("jncraton/Qwen2.5-1.5B-Instruct-ct2-int8", "Qwen 2.5 — 1.5B", "1.5 GB",
            "Rapide, bon pour corriger et mettre en forme", "Fast, good for fixing and formatting"),
    LlmInfo("jncraton/Qwen2.5-3B-Instruct-ct2-int8", "Qwen 2.5 — 3B", "3.1 GB",
            "★ Recommandé : bien meilleur pour reformuler", "★ Recommended: much better at rewriting"),
    LlmInfo("jncraton/Qwen2.5-7B-Instruct-ct2-int8", "Qwen 2.5 — 7B", "7.6 GB",
            "Le plus intelligent, mais lourd (PC puissant)", "Smartest, but heavy (powerful PC)"),
]
DEFAULT_LLM = LLM_CATALOG[1].source
_PATTERNS = ["*.json", "model.bin"]

SYSTEM_FR = (
    "Tu es un assistant de mise en forme de dictée vocale. Tu reçois la transcription brute de ce "
    "qu'une personne a dicté. Réécris-la en suivant exactement les consignes. Règles absolues : "
    "ne réponds jamais au contenu comme si on te parlait, n'invente aucune information, ne commente "
    "pas, n'ajoute pas de guillemets ni de titre. Écris dans la même langue que la dictée. "
    "La dictée contient souvent des indications qui te sont destinées, par exemple « courriel à "
    "[personne] pour lui dire que… » ou « dis à [personne] que… » : utilise-les (destinataire, "
    "intention) mais ne les recopie jamais ; rédige directement le message, à la première personne, "
    "adressé au destinataire. N'utilise jamais un nom qui n'apparaît pas dans la dictée. "
    "Renvoie uniquement le texte final."
)

# One worked example (few-shot): small models follow the format much better with it.
EXAMPLE_IN = ("euh courriel à madame Gagnon pour lui dire que j'ai bien reçu sa soumission et que je "
              "la regarde cette semaine et euh aussi lui demander si le prix inclut la livraison")
EXAMPLE_RULES = ("Salutation « Bonjour Madame X, », petits paragraphes de 1 à 2 phrases séparés par une "
                 "ligne vide, formule de politesse puis la signature : Paul")
EXAMPLE_OUT = ("Bonjour Madame Gagnon,\n\nJ'ai bien reçu votre soumission, merci. Je la regarde cette "
               "semaine.\n\nPourriez-vous me confirmer si le prix inclut la livraison ?\n\nMerci,\n\nPaul")


def is_downloaded(source: str) -> bool:
    try:
        path = Path(snapshot_download(source, allow_patterns=_PATTERNS, local_files_only=True))
        return (path / "model.bin").exists() and (path / "tokenizer.json").exists()
    except Exception:  # noqa: BLE001
        return False


def download(source: str) -> str:
    return snapshot_download(source, allow_patterns=_PATTERNS)


def new_preset_id() -> str:
    return uuid.uuid4().hex[:8]


def default_presets(ui: str) -> list[dict]:
    if ui != "fr":
        return [
            {"id": "email", "name": "Email", "hotkey": "f2", "instructions": (
                "Format this dictation as a professional email.\n"
                "- Start with a greeting: \"Hello Mr. X,\" or \"Hello Ms. X,\" (title + last name only) if "
                "the recipient is named in the dictation; if no name is dictated, just write \"Hello,\".\n"
                "- Split each main idea into short paragraphs of 1 to 2 sentences, with a blank line between them.\n"
                "- Fix grammar and punctuation and remove hesitations (um, so, like…) without changing the meaning.\n"
                "- No subject line.\n"
                "- End with a short closing (\"Thank you,\" or \"Best regards,\") followed by this exact signature:\n"
                "{signature}")},
            {"id": "message", "name": "Quick message", "hotkey": "f3", "instructions": (
                "Rewrite as a short, natural chat message (Teams, text) addressed directly to the person: if "
                "the dictation says \"tell Mark that…\", start with \"Hi Mark,\" and write the message to Mark. "
                "Fix mistakes and punctuation, remove hesitations and fillers (um, like…), keep a friendly "
                "tone, no signature.")},
            {"id": "notes", "name": "Bullet notes", "hotkey": "f4", "instructions": (
                "Turn the dictation into clear notes as a bulleted list (\"- \"), one idea per line, short "
                "sentences, no introduction or conclusion.")},
            {"id": "fix", "name": "Fix only", "hotkey": "", "instructions": (
                "Only fix grammar, spelling and punctuation and remove hesitations. Do not rephrase.")},
        ]
    return [
        {"id": "email", "name": "Courriel", "hotkey": "f2", "instructions": (
            "Mets cette dictée en forme de courriel professionnel.\n"
            "- Commence par une salutation : « Bonjour Monsieur X, » ou « Bonjour Madame X, » (civilité + "
            "nom de famille seulement) si le destinataire est nommé dans la dictée ; si aucun nom n'est "
            "dicté, écris simplement « Bonjour, ».\n"
            "- Sépare chaque idée principale en petits paragraphes de 1 à 2 phrases, avec une ligne vide "
            "entre les paragraphes.\n"
            "- Corrige la grammaire et la ponctuation et retire les hésitations (euh, donc, genre…) sans "
            "changer le sens.\n"
            "- N'écris pas d'objet.\n"
            "- Termine par une formule de politesse courte (« Merci, » ou « Bonne journée, ») suivie "
            "exactement de cette signature :\n"
            "{signature}")},
        {"id": "message", "name": "Message rapide", "hotkey": "f3", "instructions": (
            "Réécris comme un message court et naturel (Teams, texto) adressé directement à la personne : "
            "si la dictée dit « dis à Marc que… », commence par « Salut Marc, » et écris le message à Marc. "
            "Corrige les fautes et la ponctuation, retire les hésitations et les tics (euh, genre…), garde un "
            "ton amical, sans signature.")},
        {"id": "notes", "name": "Notes en points", "hotkey": "f4", "instructions": (
            "Transforme la dictée en notes claires sous forme de liste à puces (« - »), une idée par ligne, "
            "phrases courtes, sans introduction ni conclusion.")},
        {"id": "fix", "name": "Correction seule", "hotkey": "", "instructions": (
            "Corrige seulement la grammaire, l'orthographe et la ponctuation et retire les hésitations. "
            "Ne reformule pas.")},
    ]


class Writer:
    def __init__(self, source: str, device: str = "auto", cpu_compute: str = "int8",
                 gpu_compute: str = "int8_float16"):
        self.source = source
        path = download(source)
        self.tokenizer = Tokenizer.from_file(str(Path(path) / "tokenizer.json"))
        self.gpu_error: str | None = None
        want_gpu = device == "cuda" or (device == "auto" and gpu.cuda_available())
        if want_gpu:
            try:
                self.generator = ctranslate2.Generator(path, device="cuda", compute_type=gpu_compute)
                self.device = "cuda"
                self._generate("ok", "Réponds ok.", max_tokens=2)  # warm-up: fails here if CUDA is broken
                return
            except Exception as exc:  # noqa: BLE001
                self.gpu_error = str(exc)
        self.generator = ctranslate2.Generator(path, device="cpu", compute_type=cpu_compute)
        self.device = "cpu"

    def _generate(self, user: str, system: str, max_tokens: int = 1024,
                  shots: list[tuple[str, str]] = ()) -> str:
        prompt = f"<|im_start|>system\n{system}<|im_end|>\n"
        for q, a in shots:
            prompt += f"<|im_start|>user\n{q}<|im_end|>\n<|im_start|>assistant\n{a}<|im_end|>\n"
        prompt += f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
        tokens = self.tokenizer.encode(prompt, add_special_tokens=False).tokens
        result = self.generator.generate_batch(
            [tokens], max_length=max_tokens, sampling_topk=1, repetition_penalty=1.05,
            include_prompt_in_result=False, end_token=["<|im_end|>", "<|endoftext|>"],
        )
        return self.tokenizer.decode(result[0].sequences_ids[0], skip_special_tokens=True).strip()

    def rewrite(self, text: str, instructions: str, signature: str = "") -> str:
        if not text.strip():
            return text
        rules = instructions.replace("{signature}", signature.strip() or "(pas de signature)")

        def ask(r: str, t: str) -> str:
            return f"Consignes :\n{r}\n\nTranscription brute à réécrire :\n{t}"

        out = self._generate(ask(rules, text), SYSTEM_FR, max_tokens=max(256, len(text) // 2 + 400),
                             shots=[(ask(EXAMPLE_RULES, EXAMPLE_IN), EXAMPLE_OUT)])
        return out.strip().strip("«»\"").strip() or text
