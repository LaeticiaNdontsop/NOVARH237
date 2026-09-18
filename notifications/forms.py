from django import forms

from accounts.models import Utilisateur


class NotificationForm(forms.Form):
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Saisissez le message ou l'alerte a diffuser..."}),
    )
    role_cible = forms.ChoiceField(
        label="Cible",
        choices=[
            ("TOUS", "Tous"),
            ("EMPLOYE", "Employes"),
            ("RH", "Responsables RH"),
            ("ADMIN", "Administrateurs"),
        ],
        initial="TOUS",
    )
    destinataire = forms.ModelChoiceField(
        label="Destinataire precis (optionnel)",
        queryset=Utilisateur.objects.none(),
        required=False,
        empty_label="Tous les utilisateurs de la cible",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destinataire"].queryset = Utilisateur.objects.order_by("last_name", "first_name", "username")
