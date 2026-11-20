"""Writer.rewrite with a fake model: the signature and the subject are handled by code, not by the AI."""

import pytest

writer = pytest.importorskip("voice_typer.writer")


class FakeWriter(writer.Writer):
    def __init__(self, body, subject="Livraison retardée"):
        self.body, self.subject, self.calls = body, subject, []

    def _generate(self, user, system, max_tokens=1024, shots=()):
        self.calls.append((user, system))
        return self.subject if system == writer.SUBJECT_SYSTEM else self.body


RULES = ("Mets en forme de courriel.\n- Toujours signer telle que mentionnée, mais si j'ai dicté ma propre "
         "signature, ne pas mettre la signature enregistrée.\n- Génère un titre de courriel.")


def test_signature_and_subject_by_code():
    w = FakeWriter("Bonjour Marc,\n\nLa livraison est retardée à jeudi.\n\nMerci,\n(aucune signature)")
    out = w.rewrite("courriel à Marc pour dire que la livraison est retardée", RULES, "Hugo Dasilva",
                    add_signature=True, subject=True)
    assert out == ("Objet : Livraison retardée\n\nBonjour Marc,\n\nLa livraison est retardée à jeudi.\n\n"
                   "Merci,\nHugo Dasilva")
    prompt = w.calls[0][0]
    assert "signature" not in prompt.split("Transcription brute")[0].lower()   # rules sent without it
    assert "titre" not in prompt.lower()


def test_dictated_signature_not_doubled_and_no_subject_when_off():
    w = FakeWriter("Bonjour,\n\nC'est noté.\n\nMerci,\nHugo pour l'équipe Ventes")
    out = w.rewrite("dictée", RULES, "Hugo Dasilva", add_signature=True, subject=False)
    assert out.endswith("Merci,\nHugo pour l'équipe Ventes") and "Hugo Dasilva" not in out
    assert len(w.calls) == 1                                                  # no subject request


class LangWriter(FakeWriter):
    """Answers in French first (like the small model did), then obeys "Answer in English only"."""

    def _generate(self, user, system, max_tokens=1024, shots=()):
        self.calls.append((user, system))
        if system in (writer.SUBJECT_SYSTEM, writer.SUBJECT_SYSTEM_EN):
            return "Test request"
        if "English only" in system:
            return self.body
        return ("Je voudrais effectuer un test.\n\nPourriez-vous me confirmer si le prix inclut la "
                "livraison ?\n\nMerci,")


def test_english_dictation_gets_an_english_email_and_signature():
    w = LangWriter("Hello,\n\nI would like to do a test.\n\nThank you,")
    out = w.rewrite("Hi, I would like to do a test.", RULES, "Hugo Da Silva\nDirecteur de comptes", True, True,
                    signature_en="Hugo Da Silva\nAccount Manager", language="fr")
    assert out == ("Subject: Test request\n\nHello,\n\nI would like to do a test.\n\nThank you,\n"
                   "Hugo Da Silva\nAccount Manager")
    assert w.calls[0][1] == writer.SYSTEM_EN and "Raw transcript" in w.calls[0][0]
    assert writer.EN_RULES_NOTE in w.calls[0][0]


def test_french_dictation_keeps_the_french_signature():
    w = FakeWriter("Bonjour,\n\nC'est noté pour jeudi.\n\nMerci,")
    out = w.rewrite("dis-lui que c'est noté pour jeudi", RULES, "Hugo Da Silva", True, False,
                    signature_en="Hugo Da Silva (EN)", language="en")
    assert out.endswith("Merci,\nHugo Da Silva") and w.calls[0][1] == writer.SYSTEM_FR


def test_english_signature_falls_back_to_the_main_one():
    w = FakeWriter("Hello,\n\nNoted for Thursday.\n\nThank you,")
    assert w.rewrite("tell him it's noted for Thursday", RULES, "Hugo", True, False).endswith("Thank you,\nHugo")


def test_sentences_copied_from_the_example_are_removed():
    out = writer.drop_copied_example("Bonjour,\n\nJe voudrais faire un test.\n\nPourriez-vous me confirmer si le "
                                     "prix inclut la livraison ?\n\nMerci,", "je voudrais faire un test",
                                     writer.EXAMPLE_OUT)
    assert out == "Bonjour,\n\nJe voudrais faire un test.\n\nMerci,"
    # dictated for real: kept
    real = "Bonjour,\n\nPourriez-vous me confirmer si le prix inclut la livraison ?\n\nMerci,"
    assert writer.drop_copied_example(real, "demande si le prix inclut la livraison", writer.EXAMPLE_OUT) == real
