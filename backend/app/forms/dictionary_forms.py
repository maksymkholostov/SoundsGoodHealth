from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

class NewDictionaryForm(FlaskForm):
    """Form for creating a new dictionary."""
    name = StringField(
        'Dictionary Name', 
        validators=[
            DataRequired(message="Please provide a dictionary name."), 
            Length(min=1, max=100, message="Name must be between 1 and 100 characters.")
        ],
        render_kw={"placeholder": "e.g., Vowel Sounds Practice"}
    )
    description = TextAreaField(
        'Description',
        validators=[Length(max=500)],
        render_kw={"placeholder": "Optional: Describe the purpose or contents of this dictionary."}
    )
    # Note: Class selection/creation handled separately in the template/JS for now, not as WTForms fields.
    submit = SubmitField('Create Dictionary')

# You might add other forms here later, e.g., EditDictionaryForm 