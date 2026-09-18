from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="login"),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("utilisateurs/", views.ListeUtilisateursView.as_view(), name="liste_utilisateurs"),
    path("utilisateurs/nouveau/", views.CreationUtilisateurView.as_view(), name="creer_utilisateur"),
    path("profil/", views.ProfilView.as_view(), name="profil"),
    path("mot-de-passe/", views.ChangerMotDePasseView.as_view(), name="changer_mot_de_passe"),
]
