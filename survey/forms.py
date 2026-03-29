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
