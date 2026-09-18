"""
Construction du CONTEXTE transmis a l'assistant conversationnel (CDC §6.5.10,
RG-15 : "l'assistant IA ne doit pas donner acces a des informations auxquelles
l'utilisateur n'est pas autorise").

Principe de conception : l'assistant IA n'a JAMAIS d'acces direct a la base de
donnees (pas d'agent, pas d'appel de fonction cote modele). A chaque question,
NOVA RH construit d'abord, cote serveur, un texte de contexte qui ne contient
QUE ce que le role de l'utilisateur connecte l'autorise deja a voir ailleurs
dans l'application (RG-06). Ce texte est ensuite transmis a Gemini avec une
consigne stricte de ne repondre qu'a partir de ce contenu. Ainsi, meme si le
modele se trompait ou etait manipule par la question posee, il ne pourrait
techniquement pas reveler une information qui ne lui a pas ete fournie.
"""
from demandes.models import Absence, DemandeConge, Demission, StatutAbsence, StatutDemande, StatutDemission
from employees.models import Employe, StatutEmploye

from . import indicateurs

MAX_EMPLOYES_LISTES = 60
MAX_LIGNES_PAR_LISTE = 15


def _section_indicateurs():
    ind = indicateurs.indicateurs_tableau_de_bord()
    lignes = [
        "INDICATEURS RH GLOBAUX (calcules a l'instant, agreges - RG-14) :",
        f"- Effectif actif : {ind['effectif_actif']}",
        f"- Taux d'absenteisme du mois en cours : {ind['taux_absenteisme_mois']}%",
        f"- Turnover (12 derniers mois) : {ind['turnover_12_mois']}%",
    ]
    if ind["taux_acceptation_conges"] is not None:
        lignes.append(f"- Taux d'acceptation des conges (12 derniers mois) : {ind['taux_acceptation_conges']}%")
    else:
        lignes.append("- Taux d'acceptation des conges : pas encore assez de demandes cloturees pour le calculer.")
    if ind["repartition_par_service"]:
        rep = ", ".join(f"{r['service']} : {r['total']}" for r in ind["repartition_par_service"])
        lignes.append(f"- Repartition de l'effectif actif par service : {rep}")
    return "\n".join(lignes)


def contexte_pour_employe(employe):
    """Un Employe (ou un Responsable RH agissant pour son propre espace) ne voit que SES donnees."""
    lignes = [
        "PROFIL DE L'UTILISATEUR CONNECTE (role Employe) :",
        f"- Nom : {employe.nom_complet}",
        f"- Matricule : {employe.matricule}",
        f"- Poste : {employe.poste} ({employe.service})",
        f"- Date d'embauche : {employe.date_embauche}",
        f"- Statut : {employe.get_statut_display()}",
    ]
    derniere_remuneration = employe.remunerations.first()
    if derniere_remuneration:
        lignes.append(
            f"- Derniere remuneration totale connue : {derniere_remuneration.total} FCFA "
            f"(effective au {derniere_remuneration.date_effective})"
        )

    lignes.append("\nSES DEMANDES DE CONGE/PERMISSION RECENTES :")
    demandes = list(employe.demandes_conge.all()[:MAX_LIGNES_PAR_LISTE])
    if demandes:
        for d in demandes:
            lignes.append(f"- {d.get_type_demande_display()} du {d.date_debut} au {d.date_fin} : {d.get_statut_display()}")
    else:
        lignes.append("- Aucune demande enregistree.")

    lignes.append("\nSES ABSENCES RECENTES :")
    absences = list(employe.absences.all()[:MAX_LIGNES_PAR_LISTE])
    if absences:
        for a in absences:
            lignes.append(f"- Du {a.date_debut} au {a.date_fin} : {a.get_statut_display()}")
    else:
        lignes.append("- Aucune absence declaree.")

    demission = getattr(employe, "demission", None)
    if demission:
        details = f"statut {demission.get_statut_display()}"
        if demission.preavis_jours is not None:
            details += f", preavis fixe a {demission.preavis_jours} jour(s)"
        lignes.append(f"\nSA DECLARATION DE DEMISSION : {details}.")

    lignes.append(
        "\nRAPPEL IMPORTANT : cet utilisateur a le role Employe. Il n'a acces qu'a ses propres "
        "informations. Ne mentionne jamais de nom, salaire, demande ou document d'un AUTRE employe : "
        "de toute facon, aucune de ces informations ne t'a ete transmise ci-dessus."
    )
    return "\n".join(lignes)


def contexte_pour_rh_ou_admin(utilisateur):
    """
    Le Responsable RH et l'Administrateur ont une vue d'ensemble (BF-RH-17/18, BF-ADM06),
    mais RG-05 : meme le Responsable RH n'a pas acces aux documents des AUTRES employes -
    ces documents ne figurent donc jamais dans ce contexte, quel que soit le role.
    Les salaires individuels ne sont pas non plus listes un par un ici (seule une agregation
    par service pourrait etre ajoutee plus tard) : cela limite l'exposition d'une donnee
    tres sensible (RG-12) dans un prompt, sans retirer au RH/Admin l'acces qu'il a deja par
    ailleurs via les fiches employes.
    """
    lignes = [f"UTILISATEUR CONNECTE : {utilisateur.get_full_name()} ({utilisateur.get_role_display()})", ""]
    lignes.append(_section_indicateurs())

    total_actifs = Employe.objects.filter(statut=StatutEmploye.ACTIF).count()
    lignes.append("\nEMPLOYES ACTIFS (liste, sans donnees salariales individuelles) :")
    employes = Employe.objects.select_related("utilisateur").filter(statut=StatutEmploye.ACTIF)[:MAX_EMPLOYES_LISTES]
    for e in employes:
        lignes.append(f"- {e.matricule} | {e.nom_complet} | {e.poste} | {e.service} | embauche le {e.date_embauche}")
    if total_actifs > MAX_EMPLOYES_LISTES:
        lignes.append(f"... et {total_actifs - MAX_EMPLOYES_LISTES} autre(s) employe(s) actif(s) non detailles ici.")

    lignes.append("\nDEMANDES DE CONGE/PERMISSION EN ATTENTE DE TRAITEMENT :")
    en_attente = list(DemandeConge.objects.exclude(
        statut__in=[StatutDemande.APPROUVEE, StatutDemande.REJETEE_RH, StatutDemande.REJETEE_ADMIN]
    ).select_related("employe__utilisateur")[:MAX_LIGNES_PAR_LISTE])
    if en_attente:
        for d in en_attente:
            lignes.append(f"- {d.employe.nom_complet} : {d.get_type_demande_display()} du {d.date_debut} au {d.date_fin}, {d.get_statut_display()}")
    else:
        lignes.append("- Aucune demande en attente.")

    lignes.append("\nABSENCES EN ATTENTE DE VALIDATION :")
    absences_attente = list(Absence.objects.filter(statut=StatutAbsence.EN_ATTENTE).select_related("employe__utilisateur")[:MAX_LIGNES_PAR_LISTE])
    if absences_attente:
        for a in absences_attente:
            lignes.append(f"- {a.employe.nom_complet} : du {a.date_debut} au {a.date_fin}")
    else:
        lignes.append("- Aucune absence en attente.")

    lignes.append("\nDEMISSIONS EN COURS DE TRAITEMENT :")
    demissions = list(Demission.objects.exclude(statut=StatutDemission.COMMUNIQUEE).select_related("employe__utilisateur")[:MAX_LIGNES_PAR_LISTE])
    if demissions:
        for d in demissions:
            lignes.append(f"- {d.employe.nom_complet} : {d.get_statut_display()}")
    else:
        lignes.append("- Aucune demission en cours de traitement.")

    lignes.append(
        "\nRAPPEL IMPORTANT (RG-05/RG-12) : les documents personnels des employes (CNI, diplomes, "
        "bulletins de paie...) et les salaires individuels ne figurent jamais dans ce contexte : "
        "ne les invente jamais, et redirige l'utilisateur vers la fiche employe correspondante dans "
        "NOVA RH s'il a besoin de ce niveau de detail."
    )
    return "\n".join(lignes)


def construire_contexte(utilisateur):
    """Point d'entree unique : construit le contexte adapte au role connecte (RG-06 / RG-15)."""
    if utilisateur.peut_gerer_employes:
        return contexte_pour_rh_ou_admin(utilisateur)
    employe = getattr(utilisateur, "fiche_employe", None)
    if employe is not None:
        return contexte_pour_employe(employe)
    return f"UTILISATEUR CONNECTE : {utilisateur.get_full_name()}. Aucune fiche employe associee a ce compte."
