from django import forms

from site_settings.models import QuickLink, SiteSettings


class SiteSettingsBrandingForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ['branding_text', 'brand_mark', 'brand_mark_dark']
        widgets = {
            # size= ustawia wizualną szerokość input'a tak by zmieścił max_length znaków bez przewijania
            'branding_text': forms.TextInput(attrs={'size': SiteSettings._meta.get_field('branding_text').max_length}),
        }


class QuickLinkForm(forms.ModelForm):
    class Meta:
        model = QuickLink
        fields = ['title', 'url', 'icon', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'size': 50}),
            'url': forms.TextInput(attrs={'size': 80}),
            'icon': forms.TextInput(attrs={'size': 30}),
            'order': forms.NumberInput(attrs={'size': 5}),
        }
