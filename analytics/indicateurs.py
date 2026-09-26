"""
Calcul des indicateurs RH agreges (CDC §6.5.9, BF-RH-17 / BF-RH-18) :
effectif, taux d'absenteisme, turnover, taux d'acceptation des conges.

RG-14 : ces indicateurs sont des AGREGATS (comptages, moyennes, pourcentages) ;
aucune donnee individuelle sensible (salaire d'une personne, contenu d'un
document...) n'est exposee ici. Ils peuvent donc etre affiches a tout
Responsable RH ou Administrateur sans jamais depasser les droits d'acces
attaches a une fiche employe en particulier.
"""
import calendar
from datetime import date, timedelta

from django.db.models import Count
from django.utils import timezone

from demandes.models import Absence, DemandeConge, Demission, StatutAbsence, StatutDemande, StatutDemission, TypeDemande
from employees.models import Employe, StatutEmploye

MOIS_ABBR_FR = ["", "Jan", "Fev", "Mar", "Avr", "Mai", "Jun", "Jul", "Aou", "Sep", "Oct", "Nov", "Dec"]


def _jours_ouvrables(annee, mois):
    """Nombre de jours ouvres (lundi a vendredi) dans un mois donne."""
    nb_jours = calendar.monthrange(annee, mois)[1]
    return sum(1 for jour in range(1, nb_jours + 1) if date(annee, mois, jour).weekday() < 5)


def effectif_actif():
    return Employe.objects.filter(statut=StatutEmploye.ACTIF).count()


def taux_absenteisme(annee=None, mois=None):
    """
    Taux d'absenteisme du mois (par defaut le mois courant), calcule sur les absences declarees :

        (somme des jours d'absence declaree du mois) / (effectif actif x jours ouvres du mois) x 100

    Les absences qui chevauchent partiellement le mois ne comptent que pour
    leurs jours effectivement compris dans le mois (les bornes sont "clippees").
    Hypothese assumee : l'effectif actif ACTUEL sert d'approximation de
    l'effectif du mois concerne (pas d'historique d'effectif jour par jour).
    """
    aujourdhui = timezone.localdate()
    annee = annee or aujourdhui.year
    mois = mois or aujourdhui.month

    debut_mois = date(annee, mois, 1)
    fin_mois = date(annee, mois, calendar.monthrange(annee, mois)[1])

    capacite = effectif_actif() * _jours_ouvrables(annee, mois)
    if capacite == 0:
        return 0.0

    jours_absence = 0
    absences = Absence.objects.filter(
        statut=StatutAbsence.DECLAREE, date_debut__lte=fin_mois, date_fin__gte=debut_mois
    )
    for absence in absences:
        debut = max(absence.date_debut, debut_mois)
        fin = min(absence.date_fin, fin_mois)
        jours_absence += (fin - debut).days + 1

    return round(min(jours_absence / capacite * 100, 100), 1)


def turnover(nb_mois=12):
    """
    Turnover glissant sur `nb_mois` (formule RH classique) :

        departs / effectif moyen x 100

    L'effectif en debut de periode est reconstitue a partir de l'effectif actuel,
    des departs et des embauches survenus depuis : c'est une approximation
    raisonnable en l'absence d'un historique d'effectif jour par jour, a
    documenter comme telle lors de la soutenance.
    """
    depuis = timezone.now() - timedelta(days=30 * nb_mois)
    effectif_actuel = effectif_actif()

    departs = Employe.objects.filter(statut=StatutEmploye.INACTIF, date_desactivation__gte=depuis).count()
    embauches = Employe.objects.filter(date_embauche__gte=depuis.date()).count()

    effectif_debut = max(effectif_actuel - embauches + departs, 0)
    effectif_moyen = (effectif_debut + effectif_actuel) / 2
    if effectif_moyen == 0:
        return 0.0
    return round(min(departs / effectif_moyen * 100, 100), 1)


def taux_acceptation_conges(nb_mois=12, type_demande=TypeDemande.CONGE):
    """
    Parmi les demandes CLOTUREES (approuvees ou rejetees, quelle que soit
    l'etape ou elles ont ete rejetees) sur la periode : proportion d'approuvees.
    Retourne None si aucune demande cloturee sur la periode, pour permettre a
    l'affichage de montrer "pas encore de donnees" plutot qu'un 0% trompeur.
    """
    depuis = timezone.now() - timedelta(days=30 * nb_mois)
    cloturees = DemandeConge.objects.filter(
        type_demande=type_demande,
        statut__in=[StatutDemande.APPROUVEE, StatutDemande.REJETEE_RH, StatutDemande.REJETEE_ADMIN],
        date_soumission__gte=depuis,
    )
    total = cloturees.count()
    if total == 0:
        return None
    approuvees = cloturees.filter(statut=StatutDemande.APPROUVEE).count()
    return round(approuvees / total * 100, 1)


def repartition_par_service():
    """Effectif actif par service (agregat, RG-14) - pour un petit graphique en barres."""
    return list(
        Employe.objects.filter(statut=StatutEmploye.ACTIF)
        .values("service").annotate(total=Count("id")).order_by("-total")
    )


def historique_mensuel(nb_mois=6):
    """Taux d'absenteisme mois par mois, pour un mini graphique en barres (CSS pur, sans JS)."""
    aujourdhui = timezone.localdate()
    resultats = []
    annee, mois = aujourdhui.year, aujourdhui.month
    for _ in range(nb_mois):
        taux = taux_absenteisme(annee, mois)
        resultats.append({
            "label": f"{MOIS_ABBR_FR[mois]} {annee}",
            "taux_absenteisme": taux,
            # Hauteur d'affichage pour le mini graphique en barres (plafonnee a
            # 20% d'absenteisme = barre pleine, pour rester lisible meme si un
            # mois isole depasse largement la moyenne).
            "hauteur_affichage": round(min(taux, 20) / 20 * 100, 1),
        })
        mois -= 1
        if mois == 0:
            mois, annee = 12, annee - 1
    resultats.reverse()
    return resultats


def demandes_en_attente_par_type():
    return {
        "conges_permissions": DemandeConge.objects.exclude(
            statut__in=[StatutDemande.APPROUVEE, StatutDemande.REJETEE_RH, StatutDemande.REJETEE_ADMIN]
        ).count(),
        "absences": Absence.objects.filter(statut=StatutAbsence.DECLAREE).count(),
        "demissions": Demission.objects.exclude(statut=StatutDemission.COMMUNIQUEE).count(),
    }


def indicateurs_tableau_de_bord():
    """Point d'entree unique utilise par la vue du tableau de bord et par l'assistant IA."""
    return {
        "effectif_actif": effectif_actif(),
        "taux_absenteisme_mois": taux_absenteisme(),
        "turnover_12_mois": turnover(),
        "taux_acceptation_conges": taux_acceptation_conges(),
        "repartition_par_service": repartition_par_service(),
        "historique_absenteisme": historique_mensuel(),
        "demandes_en_attente": demandes_en_attente_par_type(),
    }


# ---------------------------------------------------------------------------
# Effectifs dans le temps et par departement (tableaux de bord, analyse intelligente)
# Reconstitues a partir des dates d'embauche et de desactivation des fiches.
# ---------------------------------------------------------------------------
def _fin_de_mois(annee, mois):
    return date(annee, mois, calendar.monthrange(annee, mois)[1])


def effectif_a_la_date(jour, service=None):
    """Nombre d'employes en poste a `jour` (embauches <= jour et non desactives avant)."""
    qs = Employe.objects.filter(date_embauche__lte=jour)
    if service is not None:
        qs = qs.filter(service=service)
    return sum(
        1 for e in qs.only("statut", "date_desactivation")
        if e.date_desactivation is None or timezone.localtime(e.date_desactivation).date() > jour
    )


def _mois_precedents(nb_mois):
    """Liste (annee, mois) des `nb_mois` derniers mois, du plus ancien au mois courant."""
    aujourdhui = timezone.localdate()
    annee, mois = aujourdhui.year, aujourdhui.month
    resultats = []
    for _ in range(nb_mois):
        resultats.append((annee, mois))
        mois -= 1
        if mois == 0:
            mois, annee = 12, annee - 1
    resultats.reverse()
    return resultats


def historique_effectif(nb_mois=6, service=None):
    """[{label, valeur}] : effectif a la fin de chacun des derniers mois (le mois courant = aujourd'hui)."""
    aujourdhui = timezone.localdate()
    points = []
    for annee, mois in _mois_precedents(nb_mois):
        fin = min(_fin_de_mois(annee, mois), aujourdhui)
        points.append({"label": f"{MOIS_ABBR_FR[mois]} {annee}", "valeur": effectif_a_la_date(fin, service)})
    return points


def courbe_svg(points, largeur=560, hauteur=220, marge=36):
    """Coordonnees d'une courbe SVG pour `points` [{label, valeur}] (aucun JavaScript necessaire)."""
    if not points:
        return {"points": [], "polyline": "", "min": 0, "max": 0}
    valeurs = [p["valeur"] for p in points]
    bas, haut = min(valeurs), max(valeurs)
    if haut == bas:
        haut, bas = haut + 1, max(bas - 1, 0)
    n = len(points)
    coordonnees = []
    for i, p in enumerate(points):
        x = marge + (largeur - 2 * marge) * (i / (n - 1) if n > 1 else 0.5)
        y = hauteur - marge - (hauteur - 2 * marge) * ((p["valeur"] - bas) / (haut - bas))
        coordonnees.append({"x": round(x, 1), "y": round(y, 1), "label": p["label"], "valeur": p["valeur"]})
    return {
        "points": coordonnees,
        "polyline": " ".join(f"{c['x']},{c['y']}" for c in coordonnees),
        "min": bas, "max": haut, "largeur": largeur, "hauteur": hauteur, "marge": marge,
    }


def variation_effectif(nb_mois=6):
    """Variation en % de l'effectif entre il y a `nb_mois` mois et aujourd'hui (None si base nulle)."""
    points = historique_effectif(nb_mois)
    if len(points) < 2 or points[0]["valeur"] == 0:
        return None
    return round((points[-1]["valeur"] - points[0]["valeur"]) / points[0]["valeur"] * 100, 1)


def embauches_du_mois():
    aujourdhui = timezone.localdate()
    return Employe.objects.filter(date_embauche__year=aujourdhui.year, date_embauche__month=aujourdhui.month).count()


PALETTE_DEPARTEMENTS = ["#0b52d9", "#0ea5a4", "#f97316", "#22c55e", "#8b5cf6", "#ec4899", "#eab308", "#64748b"]


def repartition_departements():
    """Repartition de l'effectif actif par service, avec couleur, pourcentage et degrade conique CSS."""
    lignes = repartition_par_service()
    total = sum(l["total"] for l in lignes)
    resultat, cumul, segments = [], 0.0, []
    for i, ligne in enumerate(lignes):
        couleur = PALETTE_DEPARTEMENTS[i % len(PALETTE_DEPARTEMENTS)]
        part = (ligne["total"] / total * 100) if total else 0
        resultat.append({"service": ligne["service"] or "Non renseigné", "total": ligne["total"],
                         "pourcentage": round(part, 1), "couleur": couleur})
        segments.append(f"{couleur} {cumul:.2f}% {cumul + part:.2f}%")
        cumul += part
    return {"lignes": resultat, "total": total,
            "gradient": "conic-gradient(" + ", ".join(segments) + ")" if segments else "none"}


def delai_moyen_traitement_jours():
    """Delai moyen (jours) entre la soumission et la decision finale, sur les demandes cloturees."""
    cloturees = DemandeConge.objects.filter(
        statut__in=[StatutDemande.APPROUVEE, StatutDemande.REJETEE_RH, StatutDemande.REJETEE_ADMIN]
    )
    durees = []
    for d in cloturees:
        fin = d.date_cloture or d.date_decision_admin or d.date_traitement_rh
        if fin:
            durees.append((fin - d.date_soumission).total_seconds() / 86400)
    return round(sum(durees) / len(durees), 1) if durees else None


def absences_mois_et_precedent():
    """(nombre d'absences declarees ce mois, le mois dernier)."""
    aujourdhui = timezone.localdate()
    annee, mois = aujourdhui.year, aujourdhui.month
    prec_annee, prec_mois = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    courant = Absence.objects.filter(date_debut__year=annee, date_debut__month=mois).count()
    precedent = Absence.objects.filter(date_debut__year=prec_annee, date_debut__month=prec_mois).count()
    return courant, precedent


def turnover_par_service(nb_mois=12):
    """{service: turnover en %} = departs des `nb_mois` derniers mois / effectif moyen du service."""
    depuis = timezone.now() - timedelta(days=30 * nb_mois)
    resultats = {}
    for ligne in repartition_par_service():
        service = ligne["service"]
        actifs = ligne["total"]
        departs = Employe.objects.filter(
            service=service, statut=StatutEmploye.INACTIF, date_desactivation__gte=depuis).count()
        embauches = Employe.objects.filter(service=service, date_embauche__gte=depuis.date()).count()
        debut = max(actifs - embauches + departs, 0)
        moyen = (debut + actifs) / 2
        resultats[service] = round(min(departs / moyen * 100, 100), 1) if moyen else 0.0
    return resultats


def absenteisme_par_service(annee=None, mois=None):
    """{service: taux d'absenteisme du mois en %}."""
    aujourdhui = timezone.localdate()
    annee, mois = annee or aujourdhui.year, mois or aujourdhui.month
    debut_mois, fin_mois = date(annee, mois, 1), _fin_de_mois(annee, mois)
    jours_ouvres = _jours_ouvrables(annee, mois)
    resultats = {}
    for ligne in repartition_par_service():
        service, actifs = ligne["service"], ligne["total"]
        capacite = actifs * jours_ouvres
        if not capacite:
            resultats[service] = 0.0
            continue
        total = 0
        for a in Absence.objects.filter(statut=StatutAbsence.DECLAREE, employe__service=service,
                                        date_debut__lte=fin_mois, date_fin__gte=debut_mois):
            total += (min(a.date_fin, fin_mois) - max(a.date_debut, debut_mois)).days + 1
        resultats[service] = round(min(total / capacite * 100, 100), 1)
    return resultats


SEUIL_TURNOVER_ELEVE, SEUIL_TURNOVER_MODERE = 20.0, 10.0
SEUIL_ABSENTEISME_ELEVE, SEUIL_ABSENTEISME_MODERE = 10.0, 5.0


def analyse_par_departement():
    """
    Lecture par departement fondee sur des REGLES SIMPLES et transparentes appliquees
    aux donnees reelles (turnover 12 mois, absenteisme du mois, tendance de l'effectif).
    Ce n'est pas une prediction du modele de machine learning.
    """
    turnover = turnover_par_service()
    absenteisme = absenteisme_par_service()
    lignes = []
    for service in [l["service"] for l in repartition_par_service()]:
        t, a = turnover.get(service, 0.0), absenteisme.get(service, 0.0)
        historique = historique_effectif(6, service)
        facteurs = []
        if t >= SEUIL_TURNOVER_MODERE:
            facteurs.append(f"turnover de {t} % sur 12 mois")
        if a >= SEUIL_ABSENTEISME_MODERE:
            facteurs.append(f"absentéisme de {a} % ce mois")
        tendance = historique[-1]["valeur"] - historique[0]["valeur"] if historique else 0
        if tendance < 0:
            facteurs.append("effectif en baisse")
        if t >= SEUIL_TURNOVER_ELEVE or a >= SEUIL_ABSENTEISME_ELEVE:
            niveau, couleur = "Élevé", "rouge"
            reco = "Analyser les causes des départs et des absences avec le responsable du service."
        elif t >= SEUIL_TURNOVER_MODERE or a >= SEUIL_ABSENTEISME_MODERE:
            niveau, couleur = "Modéré", "orange"
            reco = "Suivre l'évolution le mois prochain et échanger avec l'équipe."
        else:
            niveau, couleur = "Faible", "vert"
            reco = "Maintenir les bonnes pratiques."
        lignes.append({
            "service": service or "Non renseigné", "turnover": t, "absenteisme": a,
            "tendance": tendance, "niveau": niveau, "couleur": couleur,
            "facteurs": ", ".join(facteurs).capitalize() if facteurs else "Aucun signal particulier",
            "recommandation": reco, "courbe": courbe_svg(historique, largeur=110, hauteur=36, marge=4),
        })
    ordre = {"Élevé": 0, "Modéré": 1, "Faible": 2}
    lignes.sort(key=lambda l: (ordre[l["niveau"]], l["service"]))
    return lignes
