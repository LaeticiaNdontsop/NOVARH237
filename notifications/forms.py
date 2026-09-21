from django import forms

from accounts.models import Utilisateur
from employees.models import Employe
from .models import CategorieNotification


class NotificationForm(forms.Form):
    titre = forms.CharField(
        label="Titre de la notification", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ex. : Nouvelle politique de télétravail"}),
    )
    message = forms.CharField(
        label="Message", max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Rédigez votre message ici..."}),
    )
    cible = forms.ChoiceField(
        label="Destinataires",
        choices=[
            ("TOUS", "Tous les utilisateurs"),
            ("EMPLOYE", "Tous les employés"),
            ("RH", "Les Responsables RH"),
            ("ADMIN", "Les Administrateurs"),
            ("DEPARTEMENT", "Un département"),
            ("PERSONNE", "Une personne précise"),
        ],
        initial="TOUS",
    )
    departement = forms.ChoiceField(label="Département", required=False)
    destinataire = forms.ModelChoiceField(
        label="Personne", queryset=Utilisateur.objects.none(), required=False, empty_label="Choisir...",
    )
    categorie = forms.ChoiceField(
        label="Catégorie", choices=CategorieNotification.choices, initial=CategorieNotification.COMMUNICATION,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destinataire"].queryset = Utilisateur.objects.filter(is_active=True).order_by(
            "last_name", "first_name", "username")
        services = Employe.objects.exclude(service="").values_list("service", flat=True).distinct().order_by("service")
        self.fields["departement"].choices = [("", "Choisir...")] + [(s, s) for s in services]

    def clean(self):
        cleaned = super().clean()
        cible = cleaned.get("cible")
        if cible == "DEPARTEMENT" and not cleaned.get("departement"):
            self.add_error("departement", "Choisissez un département.")
        if cible == "PERSONNE" and not cleaned.get("destinataire"):
            self.add_error("destinataire", "Choisissez une personne.")
        return cleaned
