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

- Jour 2 : Conges, permissions, absences, demissions (circuit de validation a 4 etapes)
- Jour 3 : Evaluations, formations, offres, recrutement, notifications internes
- Jour 4 : Tableaux de bord, prediction d'attrition, assistant conversationnel Gemini
