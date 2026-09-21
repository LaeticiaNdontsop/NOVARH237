from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Role, Utilisateur


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


def _verifier_email_unique(form, email):
    email = (email or "").strip()
    if not email:
        return email
    doublons = Utilisateur.objects.filter(email__iexact=email)
    if form.instance.pk:
        doublons = doublons.exclude(pk=form.instance.pk)
    if doublons.exists():
        raise forms.ValidationError("Cette adresse e-mail est déjà utilisée.")
    return email


class CreationUtilisateurForm(forms.ModelForm):
    """
    BF-ADM01 : creation d'un compte utilisateur (RH ou Employe) par l'Administrateur.
    BF-ADM02 : un mot de passe temporaire est attribue ; l'utilisateur devra le changer
    a sa premiere connexion (doit_changer_mot_de_passe=True).
    """
    mot_de_passe_temporaire = forms.CharField(
        label="Mot de passe temporaire",
        widget=forms.PasswordInput(render_value=False),
        min_length=8,
        help_text="À communiquer à l'utilisateur ; il devra le changer à sa première connexion.",
    )

    class Meta:
        model = Utilisateur
        fields = ["last_name", "first_name", "email", "telephone", "username", "role", "is_active"]
        labels = {
            "last_name": "Nom",
            "first_name": "Prénom",
            "email": "E-mail",
            "telephone": "Téléphone",
            "username": "Identifiant",
            "role": "Rôle",
            "is_active": "Compte actif",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in ("last_name", "first_name", "email"):
            self.fields[champ].required = True
        self.fields["is_active"].initial = True

    def clean_email(self):
        return _verifier_email_unique(self, self.cleaned_data.get("email"))

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        utilisateur.set_password(self.cleaned_data["mot_de_passe_temporaire"])
        utilisateur.doit_changer_mot_de_passe = True
        if commit:
            utilisateur.save()
        return utilisateur


class ModificationUtilisateurForm(forms.ModelForm):
    """Modification d'un compte par l'Administrateur (identite, role, activation)."""

    class Meta:
        model = Utilisateur
        fields = ["last_name", "first_name", "email", "telephone", "role", "is_active"]
        labels = {
            "last_name": "Nom",
            "first_name": "Prénom",
            "email": "E-mail",
            "telephone": "Téléphone",
            "role": "Rôle",
            "is_active": "Compte actif",
        }

    def clean_email(self):
        return _verifier_email_unique(self, self.cleaned_data.get("email"))


class MotDePasseTemporaireForm(forms.Form):
    """BF-ADM02 : l'Administrateur attribue un nouveau mot de passe temporaire."""
    mot_de_passe_temporaire = forms.CharField(
        label="Nouveau mot de passe temporaire", min_length=8, widget=forms.PasswordInput(render_value=False)
    )


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
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Adresse e-mail",
            "telephone": "Téléphone",
            "adresse": "Adresse",
            "photo": "Photo de profil",
        }
