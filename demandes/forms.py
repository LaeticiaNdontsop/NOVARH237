from django import forms
from .models import DemandeConge, Absence, Demission


class DemandeCongeForm(forms.ModelForm):
    """BF-EMP : soumission d'une demande de conge ou de permission."""

    class Meta:
        model = DemandeConge
        fields = ["type_demande", "date_debut", "date_fin", "motif"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "type_demande": "Type de demande",
            "date_debut": "Date de debut",
            "date_fin": "Date de fin",
            "motif": "Motif",
        }

    def clean(self):
        cleaned = super().clean()
        debut, fin = cleaned.get("date_debut"), cleaned.get("date_fin")
        if debut and fin and fin < debut:
            raise forms.ValidationError("La date de fin ne peut pas etre anterieure a la date de debut.")
        return cleaned


class TraitementCommentaireForm(forms.Form):
    """Formulaire generique (commentaire) utilise pour transmettre/rejeter/approuver une demande."""
    commentaire = forms.CharField(
        label="Commentaire (optionnel)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class AbsenceForm(forms.ModelForm):
    class Meta:
        model = Absence
        fields = ["date_debut", "date_fin", "motif", "justificatif"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "date_debut": "Date de debut",
            "date_fin": "Date de fin",
            "motif": "Motif",
            "justificatif": "Justificatif (optionnel)",
        }


class DemissionForm(forms.ModelForm):
    class Meta:
        model = Demission
        fields = ["date_effective_souhaitee", "motif"]
        widgets = {"date_effective_souhaitee": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "date_effective_souhaitee": "Date de depart souhaitee",
            "motif": "Motif (optionnel)",
        }


class PreavisForm(forms.Form):
    """BF-ADM : seul l'Administrateur fixe la duree du preavis de demission."""
    preavis_jours = forms.IntegerField(label="Duree du preavis (en jours)", min_value=0)
    commentaire = forms.CharField(label="Commentaire (optionnel)", required=False, widget=forms.Textarea(attrs={"rows": 3}))
