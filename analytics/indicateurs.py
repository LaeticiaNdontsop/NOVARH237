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
    Taux d'absenteisme du mois (par defaut le mois courant) :

        (somme des jours d'absence APPROUVEE du mois) / (effectif actif x jours ouvres du mois) x 100

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
        statut=StatutAbsence.APPROUVEE, date_debut__lte=fin_mois, date_fin__gte=debut_mois
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
        "absences": Absence.objects.filter(statut=StatutAbsence.EN_ATTENTE).count(),
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
