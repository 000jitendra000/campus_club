from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    Adds role and department fields.
    """

    ORGANIZER = 'organizer'
    PARTICIPANT = 'participant'
    HOD = 'hod'

    ROLE_CHOICES = [
        (ORGANIZER, 'Event Organizer'),
        (PARTICIPANT, 'Participant'),
        (HOD, 'HOD'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=PARTICIPANT,
        help_text='Functional role of this user in the application.',
    )

    department = models.CharField(
        max_length=100,
        blank=True,
        help_text='Department of the user. Required for Organizers and HODs.',
    )

    roll_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text='Student roll number. Set when the student first applies to an event.',
    )

    # Email should be required and unique
    email = models.EmailField(unique=True, blank=False)

    def is_organizer(self):
        return self.role == self.ORGANIZER

    def is_participant(self):
        return self.role == self.PARTICIPANT

    def is_hod(self):
        return self.role == self.HOD

    def get_role_display_full(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
