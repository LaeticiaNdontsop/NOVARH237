from django import forms

# Choix des variables categorielles : recuperes directement depuis les encodeurs
# entraines (voir analytics/prediction.py -> colonnes_categorielles()), pour
# garantir que seules des valeurs connues du modele puissent etre soumises.
CHOIX_BUSINESS_TRAVEL = [(v, v) for v in ["Non-Travel", "Travel_Rarely", "Travel_Frequently"]]
CHOIX_DEPARTMENT = [(v, v) for v in ["Human Resources", "Research & Development", "Sales"]]
CHOIX_EDUCATION_FIELD = [(v, v) for v in [
    "Human Resources", "Life Sciences", "Marketing", "Medical", "Other", "Technical Degree"
]]
CHOIX_GENDER = [("Male", "Homme"), ("Female", "Femme")]
CHOIX_JOB_ROLE = [(v, v) for v in [
    "Healthcare Representative", "Human Resources", "Laboratory Technician", "Manager",
    "Manufacturing Director", "Research Director", "Research Scientist",
    "Sales Executive", "Sales Representative",
]]
CHOIX_MARITAL_STATUS = [("Single", "Celibataire"), ("Married", "Marie(e)"), ("Divorced", "Divorce(e)")]
CHOIX_OVERTIME = [("No", "Non"), ("Yes", "Oui")]


class PredictionAttritionForm(forms.Form):
    """
    BF-RH-19 : simulateur de prediction d'attrition. Les 30 champs correspondent
    exactement aux variables utilisees a l'entrainement du modele (jeu de donnees
    IBM HR Analytics). Certains champs (age, anciennete, service, sexe, salaire)
    peuvent etre pre-remplis depuis la fiche d'un employe NOVA RH ; les autres
    variables (issues du questionnaire RH americain d'origine, ex. satisfaction
    environnementale, deplacements professionnels...) restent a renseigner
    manuellement car NOVA RH ne les collecte pas nativement.
    """

    # --- Informations generales ---
    Age = forms.IntegerField(label="Age", min_value=18, max_value=65, initial=30)
    Gender = forms.ChoiceField(label="Genre", choices=CHOIX_GENDER)
    MaritalStatus = forms.ChoiceField(label="Situation matrimoniale", choices=CHOIX_MARITAL_STATUS)
    DistanceFromHome = forms.IntegerField(label="Distance domicile-travail (km)", min_value=0, max_value=50, initial=10)
    Education = forms.IntegerField(
        label="Niveau d'etudes (1=Bac, 5=Doctorat)", min_value=1, max_value=5, initial=3
    )
    EducationField = forms.ChoiceField(label="Domaine d'etudes", choices=CHOIX_EDUCATION_FIELD)

    # --- Poste et service ---
    Department = forms.ChoiceField(label="Departement", choices=CHOIX_DEPARTMENT)
    JobRole = forms.ChoiceField(label="Intitule du poste", choices=CHOIX_JOB_ROLE)
    JobLevel = forms.IntegerField(label="Niveau hierarchique (1-5)", min_value=1, max_value=5, initial=2)
    BusinessTravel = forms.ChoiceField(label="Deplacements professionnels", choices=CHOIX_BUSINESS_TRAVEL)
    OverTime = forms.ChoiceField(label="Heures supplementaires frequentes", choices=CHOIX_OVERTIME)

    # --- Anciennete et carriere ---
    TotalWorkingYears = forms.IntegerField(label="Annees d'experience totale", min_value=0, max_value=45, initial=8)
    YearsAtCompany = forms.IntegerField(label="Anciennete dans l'entreprise (annees)", min_value=0, max_value=40, initial=3)
    YearsInCurrentRole = forms.IntegerField(label="Annees dans le poste actuel", min_value=0, max_value=20, initial=2)
    YearsSinceLastPromotion = forms.IntegerField(label="Annees depuis la derniere promotion", min_value=0, max_value=15, initial=1)
    YearsWithCurrManager = forms.IntegerField(label="Annees avec le manager actuel", min_value=0, max_value=20, initial=2)
    NumCompaniesWorked = forms.IntegerField(label="Nombre d'entreprises precedentes", min_value=0, max_value=10, initial=2)
    TrainingTimesLastYear = forms.IntegerField(label="Formations suivies l'an dernier", min_value=0, max_value=6, initial=2)

    # --- Remuneration ---
    MonthlyIncome = forms.IntegerField(label="Revenu mensuel", min_value=0, initial=300000)
    DailyRate = forms.IntegerField(label="Taux journalier (reference dataset)", min_value=0, initial=800)
    HourlyRate = forms.IntegerField(label="Taux horaire (reference dataset)", min_value=0, initial=60)
    MonthlyRate = forms.IntegerField(label="Taux mensuel (reference dataset)", min_value=0, initial=15000)
    PercentSalaryHike = forms.IntegerField(label="Derniere augmentation (%)", min_value=0, max_value=30, initial=13)
    StockOptionLevel = forms.IntegerField(label="Niveau de stock-options (0-3)", min_value=0, max_value=3, initial=0)

    # --- Satisfaction et implication (echelle 1 = faible, 4 = eleve) ---
    EnvironmentSatisfaction = forms.IntegerField(label="Satisfaction environnement de travail (1-4)", min_value=1, max_value=4, initial=3)
    JobSatisfaction = forms.IntegerField(label="Satisfaction au poste (1-4)", min_value=1, max_value=4, initial=3)
    RelationshipSatisfaction = forms.IntegerField(label="Satisfaction relationnelle (1-4)", min_value=1, max_value=4, initial=3)
    JobInvolvement = forms.IntegerField(label="Implication dans le poste (1-4)", min_value=1, max_value=4, initial=3)
    WorkLifeBalance = forms.IntegerField(label="Equilibre vie pro/perso (1-4)", min_value=1, max_value=4, initial=3)
    PerformanceRating = forms.IntegerField(label="Evaluation de performance (1-4)", min_value=1, max_value=4, initial=3)

    def to_donnees_modele(self):
        """Renvoie le dictionnaire de donnees pret pour predire_attrition()."""
        return dict(self.cleaned_data)


class QuestionAssistantForm(forms.Form):
    """BF-RH-20 : question en langage naturel posee a l'assistant conversationnel."""
    question = forms.CharField(
        label="Votre question",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ex. : Combien de demandes de conge sont en attente ?"}),
        max_length=1000,
    )
