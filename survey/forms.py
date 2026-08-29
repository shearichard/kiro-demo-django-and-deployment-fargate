from django import forms


SCALE_CHOICES = [(str(i), str(i)) for i in range(1, 6)]


class SurveyResponseForm(forms.Form):
    """Dynamically builds one radio ChoiceField (1–5) per question in the survey."""

    def __init__(self, survey, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for question in survey.questions.all():
            self.fields[f"question_{question.id}"] = forms.ChoiceField(
                label=question.text,
                choices=SCALE_CHOICES,
                widget=forms.RadioSelect,
                required=False,
            )


from survey.models import Question, Survey


class SurveyForm(forms.ModelForm):
    """Form for creating and editing a Survey (name + description)."""

    class Meta:
        model = Survey
        fields = ['name', 'description']

    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        if not name or not name.strip():
            raise forms.ValidationError("Survey name cannot be blank or whitespace only.")
        return name


class QuestionForm(forms.ModelForm):
    """Form for adding a Question to a Survey."""

    class Meta:
        model = Question
        fields = ['text', 'order']
