"""
BF-RH-20 : assistant conversationnel permettant a un utilisateur autorise de
poser des questions en langage naturel sur les informations RH auxquelles il a
droit (CDC §6.5.10). Voir contexte_assistant.py pour la construction du
contexte scope par role (RG-15) : ce module ne fait QUE l'appel au modele.

IMPORTANT (paquet Python) : le paquet `google-generativeai` est deprecie par
Google (plus de correctifs de securite) au profit du nouveau SDK unifie
`google-genai` (import `from google import genai`). C'est celui-ci qui est
utilise ici et declare dans requirements.txt.

IMPORTANT (nom du modele) : les identifiants de modeles Gemini evoluent
regulierement (nouvelles versions, mises a la retraite d'anciennes versions).
Le nom utilise est donc lu depuis GEMINI_MODEL (voir .env / settings.py) et non
code en dur, pour pouvoir le mettre a jour sans toucher au code. Verifier la
liste courante sur https://ai.google.dev/gemini-api/docs/models si l'appel
echoue avec une erreur "model not found".
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

INSTRUCTION_SYSTEME = """Tu es l'assistant RH interne de NOVA RH, une plateforme de gestion RH pour une PME camerounaise.
Reponds toujours en francais, de maniere concise et professionnelle.

Regle absolue (RG-15 du cahier des charges) : tu ne dois utiliser QUE les informations fournies
dans la section CONTEXTE ci-dessous pour repondre. Si la question porte sur une information qui
n'y figure pas (par exemple les donnees d'un autre employe que celles listees, ou un document RH),
reponds clairement que tu ne disposes pas de cette information dans le systeme. N'invente et ne
suppose JAMAIS de donnee absente du contexte.

Tu es un outil d'aide a la decision, pas un decideur : pour toute question sensible (embauche,
sanction, licenciement, litige), rappelle que la decision finale revient a un responsable humain
autorise.
"""


class AssistantIndisponible(Exception):
    """Levee quand l'appel au service IA echoue - le message est destine a l'utilisateur final."""


def _construire_prompt(question, contexte, historique):
    parties = [INSTRUCTION_SYSTEME, "\nCONTEXTE (donnees auxquelles l'utilisateur connecte a droit) :", contexte]
    if historique:
        parties.append("\nECHANGES PRECEDENTS DE CETTE CONVERSATION :")
        for tour in historique:
            parties.append(f"Utilisateur : {tour['question']}")
            parties.append(f"Assistant : {tour['reponse']}")
    parties.append(f"\nNOUVELLE QUESTION DE L'UTILISATEUR : {question}")
    return "\n".join(parties)


def repondre(question, contexte, historique=None):
    """
    Retourne le texte de reponse de l'assistant, ou leve AssistantIndisponible
    avec un message deja adapte a l'affichage (sans detail technique interne,
    cf. besoin non fonctionnel 8.3).
    """
    if not settings.GEMINI_API_KEY:
        raise AssistantIndisponible(
            "L'assistant conversationnel n'est pas configure (cle API Gemini manquante)."
        )

    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - erreur d'installation, pas d'execution
        logger.exception("Paquet google-genai introuvable")
        raise AssistantIndisponible("L'assistant conversationnel n'est pas correctement installe.") from exc

    prompt = _construire_prompt(question, contexte, historique)

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        reponse = client.models.generate_content(model=settings.GEMINI_MODEL, contents=prompt)
        texte = (reponse.text or "").strip()
        if not texte:
            raise ValueError("Reponse vide renvoyee par le modele.")
        return texte
    except Exception:
        # Non-fonctionnel 8.3 : ne jamais exposer le detail technique de l'erreur a l'utilisateur.
        logger.exception("Erreur lors de l'appel a l'API Gemini")
        raise AssistantIndisponible(
            "Le service d'assistant est momentanement indisponible. Reessaie dans quelques instants."
        )
