import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def evaluations_existantes_terminees(apps, schema_editor):
    """Les evaluations deja saisies (ancien format) sont des resultats finaux."""
    Evaluation = apps.get_model("core", "Evaluation")
    Evaluation.objects.update(statut="TERMINEE")


def copier_participants(apps, schema_editor):
    """Ancienne relation M2M `participants` -> ParticipationFormation (statut CIBLE)."""
    Formation = apps.get_model("core", "Formation")
    Participation = apps.get_model("core", "ParticipationFormation")
    for formation in Formation.objects.all():
        for employe in formation.participants.all():
            Participation.objects.get_or_create(formation=formation, employe=employe)


def _note(label):
    return models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name=label,
        choices=[(1, "1/5"), (2, "2/5"), (3, "3/5"), (4, "4/5"), (5, "5/5")],
    )


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0001_initial"),
        ("core", "0001_initial"),
    ]

    operations = [
        # --- Evaluations -------------------------------------------------
        migrations.RenameField("evaluation", "titre", "periode"),
        migrations.RenameField("evaluation", "note", "note_globale"),
        migrations.AlterField(
            "evaluation", "periode",
            models.CharField(max_length=150, verbose_name="Période", help_text="Ex. : 2e trimestre 2026"),
        ),
        migrations.AlterField(
            "evaluation", "note_globale",
            models.DecimalField(blank=True, decimal_places=1, max_digits=3, null=True),
        ),
        migrations.AddField(
            "evaluation", "statut",
            models.CharField(
                max_length=20, default="EN_ATTENTE_AUTO",
                choices=[
                    ("EN_ATTENTE_AUTO", "En attente de l'auto-évaluation"),
                    ("AUTO_SOUMISE", "Auto-évaluation soumise"),
                    ("TERMINEE", "Terminée"),
                ],
            ),
        ),
        migrations.AddField("evaluation", "qualite_travail", _note("Qualité du travail")),
        migrations.AddField("evaluation", "productivite", _note("Productivité")),
        migrations.AddField("evaluation", "ponctualite", _note("Ponctualité & assiduité")),
        migrations.AddField("evaluation", "competences", _note("Compétences professionnelles")),
        migrations.AddField("evaluation", "communication", _note("Communication")),
        migrations.AddField("evaluation", "travail_equipe", _note("Travail en équipe")),
        migrations.AddField("evaluation", "organisation", _note("Organisation")),
        migrations.AddField("evaluation", "initiative", _note("Initiative")),
        migrations.AddField("evaluation", "comportement", _note("Comportement professionnel")),
        migrations.AddField(
            "evaluation", "atteinte_objectifs",
            models.PositiveSmallIntegerField(
                blank=True, null=True, verbose_name="Atteinte des objectifs (%)",
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)],
            ),
        ),
        migrations.AddField("evaluation", "auto_evaluation", models.JSONField(blank=True, default=dict)),
        migrations.AddField("evaluation", "auto_commentaire", models.TextField(blank=True)),
        migrations.AddField("evaluation", "date_auto_evaluation", models.DateTimeField(blank=True, null=True)),
        migrations.RunPython(evaluations_existantes_terminees, migrations.RunPython.noop),

        # --- Formations : ciblage + suivi de participation ----------------
        migrations.CreateModel(
            name="ParticipationFormation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("statut", models.CharField(
                    max_length=10, default="CIBLE",
                    choices=[("CIBLE", "Ciblé - à venir"), ("PARTICIPE", "A participé"), ("ABSENT", "Absent")],
                )),
                ("date_maj", models.DateTimeField(auto_now=True)),
                ("employe", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="participations_formations", to="employees.employe",
                )),
                ("formation", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="participations", to="core.formation",
                )),
            ],
            options={
                "ordering": ["employe__utilisateur__last_name", "employe__utilisateur__first_name"],
                "unique_together": {("formation", "employe")},
            },
        ),
        migrations.RunPython(copier_participants, migrations.RunPython.noop),
        migrations.RemoveField("formation", "participants"),
    ]
