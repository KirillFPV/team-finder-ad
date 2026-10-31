from django import forms
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.exceptions import ValidationError

from team_finder.validators import normalize_phone

from .models import User


class EmailMixin:
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        existing = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise ValidationError("Пользователь с таким email уже существует.")
        return email


class RegisterForm(EmailMixin, forms.ModelForm):
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["name", "surname", "email", "password"]

    def clean(self):
        data = super().clean()
        if data.get("password"):
            user = User(**{key: data.get(key, "") for key in ("name", "surname", "email")})
            try:
                password_validation.validate_password(data["password"], user)
            except ValidationError as error:
                self.add_error("password", error)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if data.get("email") and data.get("password"):
            self.user = authenticate(
                self.request, email=data["email"].strip().lower(), password=data["password"]
            )
            if self.user is None:
                raise ValidationError("Неверный имейл или пароль")
        return data


class ProfileForm(EmailMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "surname", "email", "avatar", "about", "phone", "github_url"]
        widgets = {"about": forms.Textarea(attrs={"rows": 4})}

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        if phone and User.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Этот телефон уже указан у другого пользователя.")
        return phone


class AdminUserCreationForm(EmailMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["email", "name", "surname"]


class AdminUserChangeForm(EmailMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))
