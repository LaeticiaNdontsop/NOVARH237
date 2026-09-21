import os

from django.core.exceptions import ValidationError

EXTENSIONS_AUTORISEES = {".pdf", ".jpg", ".jpeg", ".png"}
TAILLE_MAX_OCTETS = 5 * 1024 * 1024


def valider_fichier_justificatif(fichier):
    """Formats acceptes : PDF, JPG, PNG (max. 5 Mo)."""
    extension = os.path.splitext(fichier.name)[1].lower()
    if extension not in EXTENSIONS_AUTORISEES:
        raise ValidationError("Format non accepte : PDF, JPG ou PNG uniquement.")
    if fichier.size > TAILLE_MAX_OCTETS:
        raise ValidationError("Le fichier depasse la taille maximale de 5 Mo.")
