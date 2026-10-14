from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


class StudentRegistrationForm(UserCreationForm):
    """
    Public registration form for student (Participant) accounts only.
    Role is never exposed or accepted from user input — it is always
    set to PARTICIPANT on the server side.
    """

    email = forms.EmailField(
        required=True,
        label='Email Address',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'you@example.com'}),
    )

    department = forms.CharField(
        max_length=100,
        required=False,
        label='Department (optional)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Computer Science'}),
    )

    class Meta:
        model = User
        # Only expose safe, student-relevant fields. 'role' is intentionally excluded.
        fields = ('username', 'email', 'department', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email address already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.department = self.cleaned_data.get('department', '')
        # Always force PARTICIPANT — never trust user-submitted role values.
        user.role = User.PARTICIPANT
        if commit:
            user.save()
        return user
