from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, TemplateView

from .forms import ConnexionForm, CreationUtilisateurForm, ProfilForm
from .mixins import AdminRequiredMixin
from .models import Utilisateur


class ConnexionView(LoginView):
    """RG-01 : tout acces a la plateforme necessite une authentification."""
    template_name = "registration/login.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


class ListeUtilisateursView(AdminRequiredMixin, ListView):
    """BF-ADM03 : consulter/gerer les comptes existants. Reserve a l'Administrateur."""
    model = Utilisateur
    template_name = "accounts/utilisateur_list.html"
    context_object_name = "utilisateurs"
    paginate_by = 20

    def get_queryset(self):
        return Utilisateur.objects.all().order_by("-date_creation")


class CreationUtilisateurView(AdminRequiredMixin, CreateView):
    """BF-ADM01 + BF-ADM02 : creation de compte avec mot de passe temporaire."""
    model = Utilisateur
    form_class = CreationUtilisateurForm
    template_name = "accounts/utilisateur_form.html"
    success_url = reverse_lazy("accounts:liste_utilisateurs")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Compte cree pour {self.object.get_full_name()} ({self.object.get_role_display()}). "
            "Pense a lui communiquer son identifiant et son mot de passe temporaire.",
        )
        return response


class ProfilView(LoginRequiredMixin, UpdateView):
    """BF-EMP02 / BF-ADM07 / BF-RH-22 : chaque utilisateur gere son propre profil."""
    model = Utilisateur
    form_class = ProfilForm
    template_name = "accounts/profil.html"
    success_url = reverse_lazy("accounts:profil")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profil mis a jour avec succes.")
        return super().form_valid(form)


class ChangerMotDePasseView(LoginRequiredMixin, TemplateView):
    """
    Changement de mot de passe (BF-EMP02), utilise notamment apres l'attribution
    d'un mot de passe temporaire par l'Administrateur (BF-ADM02).
    """
    template_name = "accounts/changer_mot_de_passe.html"

    def get(self, request, *args, **kwargs):
        form = PasswordChangeForm(user=request.user)
        return self.render_to_response({"form": form})

    def post(self, request, *args, **kwargs):
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            user.doit_changer_mot_de_passe = False
            user.save(update_fields=["doit_changer_mot_de_passe"])
            messages.success(request, "Mot de passe modifie avec succes.")
            from django.shortcuts import redirect
            return redirect("core:redirection_dashboard")
        return self.render_to_response({"form": form})
