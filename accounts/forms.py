from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Utilisateur


class ConnexionForm(AuthenticationForm):
    """Formulaire de connexion (BF-EMP01), stylise via widget-tweaks dans le template."""
    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "nom.utilisateur"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"placeholder": "********"}),
    )


class CreationUtilisateurForm(forms.ModelForm):
    """
    BF-ADM01 : creation d'un compte utilisateur (RH ou Employe) par l'Administrateur.
    BF-ADM02 : un mot de passe temporaire est genere/attribue ; l'utilisateur devra
    le changer a la premiere connexion (doit_changer_mot_de_passe=True par defaut).
    """
    mot_de_passe_temporaire = forms.CharField(
        label="Mot de passe temporaire",
        widget=forms.PasswordInput,
        min_length=8,
        help_text="Communique a l'utilisateur ; il devra le changer a sa premiere connexion.",
    )

    class Meta:
        model = Utilisateur
        fields = ["username", "first_name", "last_name", "email", "role"]
        labels = {
            "username": "Identifiant",
            "first_name": "Prenom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
            "role": "Role",
        }

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        utilisateur.set_password(self.cleaned_data["mot_de_passe_temporaire"])
        utilisateur.doit_changer_mot_de_passe = True
        if commit:
            utilisateur.save()
        return utilisateur


class ProfilForm(forms.ModelForm):
    """
    BF-EMP02 : l'utilisateur modifie ses coordonnees personnelles et sa photo.
    Les informations professionnelles (poste, service...) ne figurent pas ici :
    elles vivent dans l'app "employees" et restent en lecture seule pour l'employe.
    """
    class Meta:
        model = Utilisateur
        fields = ["first_name", "last_name", "email", "telephone", "adresse", "photo"]
        labels = {
            "first_name": "Prenom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
            "telephone": "Telephone",
            "adresse": "Adresse",
            "photo": "Photo de profil",
        }
