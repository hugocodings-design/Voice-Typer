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
