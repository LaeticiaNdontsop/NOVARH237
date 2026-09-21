from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="login"),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("utilisateurs/", views.ListeUtilisateursView.as_view(), name="liste_utilisateurs"),
    path("utilisateurs/nouveau/", views.CreationUtilisateurView.as_view(), name="creer_utilisateur"),
    path("utilisateurs/<int:pk>/modifier/", views.ModifierUtilisateurView.as_view(), name="modifier_utilisateur"),
    path("utilisateurs/<int:pk>/mot-de-passe/", views.ReinitialiserMotDePasseView.as_view(),
         name="reinitialiser_mot_de_passe"),
    path("utilisateurs/<int:pk>/supprimer/", views.SupprimerUtilisateurView.as_view(), name="supprimer_utilisateur"),
    path("droits-d-acces/", views.DroitsAccesView.as_view(), name="droits_acces"),
    path("profil/", views.ProfilView.as_view(), name="profil"),
    path("mot-de-passe/", views.ChangerMotDePasseView.as_view(), name="changer_mot_de_passe"),
]
