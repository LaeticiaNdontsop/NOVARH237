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


class DroitRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Acces conditionne par un droit sur un module (voir accounts/droits.py).
    `action` s'applique aux requetes de lecture (GET), `action_ecriture` aux autres.
    """
    module = None
    action = "lecture"
    action_ecriture = "modification"

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        action = self.action if self.request.method in ("GET", "HEAD", "OPTIONS") else self.action_ecriture
        return user.a_droit(self.module, action)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("Vous n'avez pas les droits necessaires pour acceder a cette page.")


def droit_requis(module, lecture="lecture", ecriture="modification"):
    """Fabrique un mixin : `class MaVue(droit_requis("employes", ecriture="creation"), CreateView)`."""
    return type(f"DroitRequis_{module}_{lecture}_{ecriture}", (DroitRequiredMixin,),
                {"module": module, "action": lecture, "action_ecriture": ecriture})


def exiger_droit(user, module, action="lecture"):
    """Pour les vues fonctions : leve PermissionDenied si le droit manque."""
    if not user.is_authenticated or not user.a_droit(module, action):
        raise PermissionDenied("Vous n'avez pas les droits necessaires pour effectuer cette action.")
