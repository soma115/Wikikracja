from django import forms

from site_settings.models import QuickLink


class QuickLinkForm(forms.ModelForm):
    class Meta:
        model = QuickLink
        fields = ['title', 'url', 'icon', 'order']
        widgets = {'title': forms.TextInput(attrs={'size': 50}), 'url': forms.TextInput(attrs={'size': 80}), 'icon': forms.TextInput(attrs={'size': 30}), 'order': forms.NumberInput(attrs={'size': 5})}
