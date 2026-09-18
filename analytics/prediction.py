"""
BF-RH-19 : utiliser le prototype de prediction (regression logistique) pour obtenir
une estimation du risque de depart (attrition) d'un employe.

Modele entraine et fourni par l'etudiante sur le jeu de donnees IBM HR Analytics
(Kaggle), conformement au CDC (§6.5.7) : 30 variables, LogisticRegression avec
StandardScaler et encodeurs categoriels (LabelEncoder) sauvegardes via joblib.

IMPORTANT (rappel du CDC) : "Ce composant est une aide a la decision et ne
remplace pas une decision humaine." Le recall mesure lors de l'entrainement est
modeste (~38%), le modele detecte donc moins d'un depart reel sur deux : il doit
etre utilise comme signal d'alerte complementaire, jamais comme base unique de
decision RH.
"""
import os
import warnings

import joblib
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning

DOSSIER = os.path.join(os.path.dirname(__file__), "ml_artifacts")

# Les artefacts ont ete sauvegardes avec scikit-learn 1.7.2 (voir requirements.txt,
# ou la version DOIT etre figee). On neutralise l'avertissement de version une fois
# la compatibilite verifiee, pour ne pas polluer les logs du serveur.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=InconsistentVersionWarning)
    _modele = joblib.load(os.path.join(DOSSIER, "modele_rh.pkl"))
    _scaler = joblib.load(os.path.join(DOSSIER, "scaler.pkl"))
    _encodeurs = joblib.load(os.path.join(DOSSIER, "encodeurs.pkl"))
    _colonnes = joblib.load(os.path.join(DOSSIER, "colonnes.pkl"))

MESSAGE_AVERTISSEMENT = (
    "Estimation experimentale issue d'un modele de prediction simple (regression "
    "logistique) entraine sur un jeu de donnees historique. Ce resultat est une "
    "aide a la decision : il ne remplace en aucun cas une decision humaine."
)


def colonnes_categorielles():
    """Retourne {nom_colonne: [valeurs possibles]} pour construire le formulaire."""
    return {col: list(encodeur.classes_) for col, encodeur in _encodeurs.items()}


def colonnes_numeriques():
    """Retourne la liste des colonnes numeriques (toutes celles non categorielles)."""
    return [c for c in _colonnes if c not in _encodeurs]


def predire_attrition(donnees: dict) -> dict:
    """
    donnees : dictionnaire avec les memes cles que les colonnes utilisees a
    l'entrainement (voir `colonnes.pkl`). Retourne la prediction (0/1), la
    probabilite de depart, un niveau de risque et le message d'avertissement.
    """
    df = pd.DataFrame([donnees])

    # Appliquer les memes encodages que pendant l'entrainement
    for col, encodeur in _encodeurs.items():
        if col in df.columns:
            df[col] = encodeur.transform(df[col])

    # Remettre les colonnes dans le meme ordre que pendant l'entrainement
    df = df[_colonnes]

    df_scaled = _scaler.transform(df)

    prediction = int(_modele.predict(df_scaled)[0])
    probabilite = float(_modele.predict_proba(df_scaled)[0][1])

    if probabilite >= 0.66:
        niveau = "eleve"
    elif probabilite >= 0.33:
        niveau = "modere"
    else:
        niveau = "faible"

    return {
        "prediction": prediction,
        "probabilite_depart": round(probabilite, 3),
        "niveau_risque": niveau,
        "message": MESSAGE_AVERTISSEMENT,
    }
