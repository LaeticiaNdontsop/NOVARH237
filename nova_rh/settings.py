"""
Configuration Django du projet NOVA RH.
Cahier des charges : plateforme web intelligente de gestion et d'aide a la decision RH
pour les PME camerounaises.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "https://localhost").split(",")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "widget_tweaks",

    # Applications NOVA RH (organisation par fonctionnalites, cf. besoin non fonctionnel 8.4)
    "accounts",
    "employees",
    "core",
    "demandes",
    "analytics",
    "notifications",
    # Sera ajoutee au fil des jours :
    # "development",
    # "recruitment",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "notifications.middleware.RequeteCouranteMiddleware",
    "demandes.middleware.VerificationDelaisMiddleware",
]

ROOT_URLCONF = "nova_rh.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.coquille",
            ],
        },
    },
]

WSGI_APPLICATION = "nova_rh.wsgi.application"

# ---------------------------------------------------------------------------
# Base de donnees : PostgreSQL via Supabase (voir .env)
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    # Filet de securite : permet de demarrer en local meme sans Supabase configure
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.Utilisateur"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:redirection_dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation (interface en francais, cf. besoin non fonctionnel 8.2)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Fichiers statiques et medias (documents RH uploades)
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cle API Gemini (utilisee par l'app "analytics" au Jour 4)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Cle API Gemini (assistant conversationnel, app "analytics", Jour 4)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Nom du modele lu depuis l'environnement plutot que code en dur : les
# identifiants de modeles Gemini sont retires/renommes regulierement. Verifier
# la liste courante sur https://ai.google.dev/gemini-api/docs/models en cas
# d'erreur "model not found". gemini-3.5-flash-lite est un choix economique
# adapte a un assistant de questions/reponses simple.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

# ---------------------------------------------------------------------------
# Bloc "entreprise" du menu (une seule entreprise : pas de multi-entreprise, cf. CDC v5)
# ---------------------------------------------------------------------------
#NOM_ENTREPRISE = os.environ.get("NOM_ENTREPRISE", "Votre entreprise")
#VILLE_ENTREPRISE = os.environ.get("VILLE_ENTREPRISE", "Douala, Cameroun")
