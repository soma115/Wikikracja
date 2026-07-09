from django.urls import path

from . import views as v

app_name = 'glosowania'

urlpatterns = (
    # path('status/<int:pk>/', v.status, name='status'),
    path('details/<int:pk>/', v.details, name='details'),
    path('edit/<int:pk>/', v.edit, name='edit'),
    path('nowy/', v.dodaj, name='dodaj_nowy'),
    path('proposition/', v.proposition, name='proposition'),
    path('discussion/', v.discussion, name='discussion'),
    path('referendum/', v.referendum, name='referendum'),
    path('rejected/', v.rejected, name='rejected'),
    path('approved/', v.approved, name='approved'),
    path('parameters/', v.parameters, name='parameters'),
    path('parameters/propose/', v.parameters_propose, name='parameters_propose'),
    path('parameters/propose/<int:pk>/', v.parameters_propose, name='parameters_edit'),
    # Argument management
    path('details/<int:pk>/add-argument/', v.add_argument, name='add_argument'),
    path('argument/<int:argument_id>/edit/', v.edit_argument, name='edit_argument'),
    path('argument/<int:argument_id>/delete/', v.delete_argument, name='delete_argument'),
    path('details/<int:pk>/historia/', v.historia, name='historia'),
)
