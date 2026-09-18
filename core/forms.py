from django import forms

from employees.models import Employe
from .models import Candidature, Evaluation, Formation, Offre


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ["employe", "titre", "date_evaluation", "note", "commentaire"]
        widgets = {"date_evaluation": forms.DateInput(attrs={"type": "date"})}


class FormationForm(forms.ModelForm):
    class Meta:
        model = Formation
        fields = ["titre", "description", "date_formation", "duree_heures", "participants"]
        widgets = {"date_formation": forms.DateInput(attrs={"type": "date"})}
        labels = {"participants": "Employes inscrits"}


class OffreForm(forms.ModelForm):
    class Meta:
        model = Offre
        fields = ["poste", "type_contrat", "lieu", "description", "statut", "date_publication", "date_limite"]
        widgets = {
            "date_publication": forms.DateInput(attrs={"type": "date"}),
            "date_limite": forms.DateInput(attrs={"type": "date"}),
        }


class CandidatureForm(forms.ModelForm):
    class Meta:
        model = Candidature
        fields = ["nom_candidat", "email", "telephone", "cv"]