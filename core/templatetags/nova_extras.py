from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Conserve les filtres GET de la page en changeant/ajoutant certains parametres (ex. page)."""
    params = context["request"].GET.copy()
    for cle, valeur in kwargs.items():
        if valeur in (None, ""):
            params.pop(cle, None)
        else:
            params[cle] = valeur
    return params.urlencode()


@register.filter
def initiales(utilisateur):
    nom = (utilisateur.get_full_name() or utilisateur.username or "").split()
    return "".join(mot[0].upper() for mot in nom[:2]) or "?"


@register.filter
def taille_fichier(fichier):
    try:
        octets = fichier.size
    except (OSError, ValueError):
        return "-"
    if octets < 1024 * 1024:
        return f"{max(octets // 1024, 1)} Ko"
    return f"{octets / (1024 * 1024):.1f} Mo"


@register.filter
def extension(fichier):
    nom = getattr(fichier, "name", "") or ""
    return nom.rsplit(".", 1)[-1].upper() if "." in nom else "-"


@register.inclusion_tag("includes/menu_item.html", takes_context=True)
def menu_item(context, nom_url, libelle, icone, actifs="", badge=None):
    """Element du menu lateral ; actif si la page courante est `nom_url` ou l'un des noms de `actifs`."""
    requete = context["request"]
    correspondance = getattr(requete, "resolver_match", None)
    vue = correspondance.view_name if correspondance else ""
    noms = [nom_url] + [n.strip() for n in actifs.split(",") if n.strip()]
    from django.urls import reverse

    return {"url": reverse(nom_url), "libelle": libelle, "icone": icone, "actif": vue in noms, "badge": badge}
