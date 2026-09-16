"""
Mixins de controle d'acces par role, utilises sur les vues de toutes les apps.
Centraliser cette logique ici evite de dupliquer les verifications de role
dans chaque module (cf. besoin non fonctionnel 8.4 : architecture maintenable).
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Usage :
        class MaVue(RoleRequiredMixin, ListView):
            roles_autorises = ["ADMIN", "RH"]
    """
    roles_autorises = []

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role in self.roles_autorises

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Vous n'avez pas les droits necessaires pour acceder a cette page.")


class AdminOuRHRequiredMixin(RoleRequiredMixin):
    """Raccourci : pages accessibles a l'Administrateur ET au Responsable RH (RG-16)."""
    roles_autorises = ["ADMIN", "RH"]


class AdminRequiredMixin(RoleRequiredMixin):
    """Pages reservees exclusivement a l'Administrateur (ex : gestion des comptes, RG-03)."""
    roles_autorises = ["ADMIN"]
