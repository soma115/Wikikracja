from django import forms

from site_settings.models import QuickLink


class QuickLinkForm(forms.ModelForm):
    class Meta:
        model = QuickLink
        fields = ['title', 'url', 'order']
        widgets = {'title': forms.TextInput(attrs={'size': 50}), 'url': forms.TextInput(attrs={'size': 80}), 'order': forms.NumberInput(attrs={'size': 5})}
