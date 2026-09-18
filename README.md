# NOVA RH

Plateforme web intelligente de gestion et d'aide a la decision RH pour les PME
camerounaises. Backend Django, frontend Django Templates + Tailwind CSS v3,
base de donnees PostgreSQL (Supabase).

Ce depot correspond a l'etat du **Jour 1** : squelette du projet, authentification,
gestion des comptes utilisateurs, et module Employes complet (fiches, contrats,
remunerations, documents).

## 1. Prerequis

- Python 3.11+ (une version recente de Python 3)
- Node.js + npm (pour compiler Tailwind CSS)
- Un projet Supabase deja cree (tu l'as deja)

## 2. Installation

```bash
# Se placer dans le dossier du projet
cd nova_rh

# Creer et activer un environnement virtuel Python
python -m venv venv
source venv/bin/activate        # Sur Windows : venv\Scripts\activate

# Installer les dependances Python
pip install -r requirements.txt

# Installer Tailwind CSS (une seule fois)
npm install
```

## 3. Configuration

```bash
cp .env.example .env
```

Ouvre `.env` et renseigne :
- `SECRET_KEY` : une chaine aleatoire longue (tu peux en generer une avec
  `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
  une fois Django installe)
- `DATABASE_URL` : ta chaine de connexion Supabase (Project Settings > Database > Connection string > URI)
- `GEMINI_API_KEY` : ta cle API Gemini (utilisee a partir du Jour 4)

## 4. Compiler le CSS Tailwind

```bash
# Une fois, pour generer static/css/output.css
npm run build:css

# OU en developpement, pour recompiler automatiquement a chaque modification
npm run watch:css
```

**Important** : tant que cette etape n'a pas ete faite, les pages s'affichent sans
mise en forme (le fichier `static/css/output.css` livre est un simple placeholder).

## 5. Base de donnees

```bash
python manage.py makemigrations
python manage.py migrate
```

## 6. Creer le premier compte Administrateur

`createsuperuser` classique ne suffit pas ici car il ne renseigne pas le role
NOVA RH. Utilise plutot :

```bash
python manage.py creer_admin --username admin --email admin@novarh.cm --password UnMotDePasseSolide123 --prenom Awa --nom Admin
```

## 7. Lancer le serveur

Dans un premier terminal (si tu utilises `npm run watch:css`, garde-le ouvert dans un
second terminal) :

```bash
python manage.py runserver
```

Ouvre http://127.0.0.1:8000/ puis connecte-toi avec le compte Administrateur cree
a l'etape 6.

## 8. Premiers pas dans l'application

1. Connecte-toi en tant qu'Administrateur.
2. Va dans **Comptes utilisateurs > Nouveau compte** pour creer un compte
   Responsable RH ou Employe (BF-ADM01/BF-ADM02).
3. Va dans **Employes > Nouvelle fiche employe** pour creer la fiche RH associee
   a ce compte (BF-RH-01/BF-ADM08).
4. Depuis la fiche employe, ajoute un contrat, une remuneration et des documents.

## Structure du projet

```
nova_rh/
├── accounts/       # Comptes utilisateurs, roles, authentification
├── employees/      # Employes, contrats, remunerations, documents RH
├── core/           # Redirection et tableaux de bord par role
├── templates/       # Tous les templates HTML (Tailwind)
├── static_src/      # Source CSS Tailwind (input.css)
├── static/css/       # CSS compile (genere par npm run build:css)
└── nova_rh/         # Configuration du projet Django
```

## Prochaines etapes (Jours 2 a 4)

- Jour 2 : Conges, permissions, absences, demissions (circuit de validation a 4 etapes) — FAIT
- Prediction d'attrition (module ML) — FAIT, integre en avance sur le planning
- Jour 3 : Evaluations, formations, offres, recrutement, notifications internes
- Jour 4 : Tableaux de bord, assistant conversationnel Gemini

## Module de prediction d'attrition (analytics)

Le modele de regression logistique (entraine par l'etudiante sur le jeu de donnees
IBM HR Analytics, cf. CDC §6.5.7) est integre dans l'app `analytics`.

**Fichiers necessaires** (deja inclus dans `analytics/ml_artifacts/`) :
`modele_rh.pkl`, `scaler.pkl`, `encodeurs.pkl`, `colonnes.pkl`.

**Important** : ces fichiers ont ete sauvegardes avec **scikit-learn 1.7.2**.
`requirements.txt` fige cette version exacte (`scikit-learn==1.7.2`) : ne pas la
changer, sous peine de degrader silencieusement la fiabilite des predictions.

**Limite assumee (a mentionner en soutenance)** : le modele utilise les 29
variables du dataset public IBM HR Analytics (Age, Department, JobSatisfaction,
OverTime...). NOVA RH ne collecte pas encore nativement toutes ces variables pour
les employes camerounais. Le formulaire pre-remplit automatiquement ce qui existe
deja (age, anciennete, sexe, revenu, departement si une correspondance est trouvee)
et laisse le reste a ajuster manuellement — c'est un prototype experimental
assume comme tel par le CDC lui-meme ("aide a la decision, ne remplace pas une
decision humaine").

**Ou tester** :
- Depuis une fiche employe : bouton "Predire l'attrition"
- Acces libre (profil non lie a un employe) : menu "Prediction attrition" (RH/Admin)
- Historique des simulations : lien "Historique" en haut de la page de prediction

## Jour 2 : Conges, permissions, absences, demission

Nouvelle app **`demandes`**, qui implemente RG-19 a RG-22 :

- **Conges/permissions** : circuit Employe → Responsable RH → Administrateur → Responsable
  RH → Employe, avec statut a code couleur (orange = en attente, vert = acceptee,
  rouge = refusee).
- **Absences** : declaration par l'employe, validation directe par le Responsable RH.
- **Demission** : declaration irrevocable (jamais approuvee/refusee) ; suit le meme
  circuit en 4 etapes mais uniquement pour la determination du preavis par
  l'Administrateur.
- **Reaffectation automatique (RG-20/21)** : si l'utilisateur assigne a une etape
  n'agit pas dans les 24h, la demande est reaffectee a un autre utilisateur du meme
  role disponible ; si aucun n'est disponible, une alerte est enregistree
  (visible dans `/admin/` sous "Alertes systeme").

### Apres avoir recupere ce zip

```bash
python manage.py makemigrations
python manage.py migrate
```

(Aucune donnee existante n'est perdue : ce sont de nouvelles tables.)

### Tester le circuit de bout en bout

1. Cree au moins **un compte RH** et **un compte Employe** (avec leurs fiches
   employe) si ce n'est pas deja fait au Jour 1.
2. Connecte-toi en tant qu'**Employe** → "Conges & permissions" → nouvelle demande.
3. Connecte-toi en tant que **Responsable RH** → "Conges & permissions" → transmets
   la demande a l'Administrateur.
4. Connecte-toi en tant qu'**Administrateur** → "Conges/permissions a decider" →
   approuve ou rejette.
5. Reconnecte-toi en **RH** → "Conges & permissions" → onglet "a notifier" → cloture
   la demande. L'employe voit alors le statut passer au vert (ou au rouge en cas de refus).
6. Meme logique pour une **demission** (menu "Departs & demissions") : Employe declare
   → RH transmet → Admin fixe le preavis → RH communique → Employe voit le preavis.

### Tester la reaffectation automatique (RG-20/21)

Pour observer une reaffectation, il faut **au moins 2 comptes RH actifs** (ou 2
comptes Admin, selon l'etape testee). Astuce pour la demo sans attendre 24h : modifie
temporairement `date_limite_rh` (ou `date_limite_admin`) d'une demande directement
dans `/admin/`, mets-la dans le passe, puis lance :

```bash
python manage.py verifier_delais_demandes
```

En production, cette commande serait planifiee (cron ou Celery beat) pour s'executer
automatiquement, par exemple toutes les 30 minutes.
