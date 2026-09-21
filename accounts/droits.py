"""
Droits d'acces par module (RG-02, BF-ADM04).

Chaque role a des droits PAR DEFAUT ; l'Administrateur peut ensuite ATTRIBUER ou
REVOQUER des droits a un utilisateur precis (table DroitUtilisateur). Les droits
personnalises d'un module remplacent les droits par defaut du role pour ce module.

Les regles de circuit (qui transmet a qui, qui decide) restent portees par le role
et par l'assignation de la demande : les droits ci-dessous controlent l'acces aux
modules, pas le circuit.
"""

ACTIONS = [
    ("lecture", "Lecture"),
    ("creation", "Création"),
    ("modification", "Modification"),
    ("suppression", "Suppression"),
]

MODULES = [
    ("dashboard", "Tableau de bord"),
    ("employes", "Employés"),
    ("recrutements", "Recrutements & offres"),
    ("demandes", "Demandes"),
    ("absences", "Absences"),
    ("demissions", "Démissions"),
    ("remunerations", "Rémunérations"),
    ("formations", "Formations"),
    ("analyse", "Analyse intelligente"),
    ("assistant", "Assistant IA"),
    ("notifications", "Notifications (envoi)"),
    ("utilisateurs", "Utilisateurs"),
    ("journaux", "Journaux d'activité"),
]

CLES_MODULES = [m[0] for m in MODULES]
CLES_ACTIONS = [a[0] for a in ACTIONS]


def _d(lecture=False, creation=False, modification=False, suppression=False):
    return {"lecture": lecture, "creation": creation, "modification": modification, "suppression": suppression}


_AUCUN = _d()
_TOUT = _d(True, True, True, True)

DROITS_PAR_DEFAUT = {
    # L'Administrateur administre (comptes, droits, journal, fiches employes) et decide des
    # demandes ; le recrutement, les formations et les remunerations relevent du RH (CDC v6).
    "ADMIN": {
        **{module: _AUCUN for module in CLES_MODULES},
        "dashboard": _d(True),
        "employes": _TOUT,
        "demandes": _d(True, False, True),
        "absences": _d(True, False, True),
        "demissions": _d(True, False, True),
        "remunerations": _d(True),
        "analyse": _d(True),
        "assistant": _d(True),
        "notifications": _d(True, True),
        "utilisateurs": _TOUT,
        "journaux": _d(True),
    },
    "RH": {
        "dashboard": _d(True),
        "employes": _d(True, True, True, True),
        "recrutements": _d(True, True, True, True),
        "demandes": _d(True, False, True),
        "absences": _d(True, False, True),
        "demissions": _d(True, False, True),
        "remunerations": _d(True, True, True),
        "formations": _d(True, True, True),
        "analyse": _d(True),
        "assistant": _d(True),
        "notifications": _d(True, True),
        "utilisateurs": _AUCUN,
        "journaux": _AUCUN,
    },
    "EMPLOYE": {
        **{module: _AUCUN for module in CLES_MODULES},
        "dashboard": _d(True),
        "assistant": _d(True),
        "notifications": _d(True),
    },
}


def droits_par_defaut(role):
    return DROITS_PAR_DEFAUT.get(role, DROITS_PAR_DEFAUT["EMPLOYE"])


def droits_effectifs(utilisateur):
    """{module: {action: bool}} : droits par defaut du role, remplaces par les droits personnalises."""
    droits = {m: dict(a) for m, a in droits_par_defaut(utilisateur.role).items()}
    if utilisateur.pk:
        for perso in utilisateur.droits_personnalises.all():
            if perso.module in droits:
                droits[perso.module] = {a: getattr(perso, a) for a in CLES_ACTIONS}
    return droits
