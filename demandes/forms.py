from django import forms
from .models import DemandeConge, Absence, Demission
from .validators import valider_fichier_justificatif


class DemandeCongeForm(forms.ModelForm):
    """BF-EMP : soumission d'une demande de conge ou de permission."""

    class Meta:
        model = DemandeConge
        fields = ["type_demande", "date_debut", "date_fin", "motif", "commentaire", "piece_jointe"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "motif": forms.Textarea(attrs={"rows": 3, "maxlength": 255}),
            "commentaire": forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
        }
        labels = {
            "type_demande": "Type de demande",
            "date_debut": "Date de début",
            "date_fin": "Date de fin",
            "motif": "Motif de la demande",
            "commentaire": "Commentaire complémentaire",
            "piece_jointe": "Pièce jointe (optionnel)",
        }
        help_texts = {"piece_jointe": "Formats acceptés : PDF, JPG, PNG (max. 5 Mo)."}

    def clean_piece_jointe(self):
        fichier = self.cleaned_data.get("piece_jointe")
        if fichier and hasattr(fichier, "size"):
            valider_fichier_justificatif(fichier)
        return fichier

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
        fields = ["date_debut", "date_fin", "type_absence", "motif", "justificatif"]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date"}),
            "date_fin": forms.DateInput(attrs={"type": "date"}),
            "motif": forms.Textarea(attrs={"rows": 3, "maxlength": 255}),
        }
        labels = {
            "date_debut": "Date de début",
            "date_fin": "Date de fin",
            "type_absence": "Motif de l'absence",
            "motif": "Commentaire (optionnel)",
            "justificatif": "Justificatif (optionnel)",
        }
        help_texts = {"justificatif": "Formats acceptés : PDF, JPG, PNG (max. 5 Mo)."}

    def clean_justificatif(self):
        fichier = self.cleaned_data.get("justificatif")
        if fichier and hasattr(fichier, "size"):
            valider_fichier_justificatif(fichier)
        return fichier

    def clean(self):
        cleaned = super().clean()
        debut, fin = cleaned.get("date_debut"), cleaned.get("date_fin")
        if debut and fin and fin < debut:
            raise forms.ValidationError("La date de fin ne peut pas être antérieure à la date de début.")
        return cleaned


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
