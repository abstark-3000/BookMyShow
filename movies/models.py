from django.db import models
from django.contrib.auth.models import User

from django.db.models.signals import post_save
from django.dispatch import receiver

from django.core.exceptions import ValidationError
import re

class Genre(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    def __str__(self):
        return self.name


class Language(models.Model):

    name = models.CharField(
        max_length=50,
        unique=True
    )

    def __str__(self):
        return self.name


def validate_youtube_url(value):
    if not value:
        return
    
    # Only allow YouTube URLs — blocks any other domain
    youtube_pattern = re.compile(
        r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
    )
    
    if not youtube_pattern.match(value):
        raise ValidationError(
            'Only valid YouTube URLs are allowed. '
            'Example: https://www.youtube.com/watch?v=xxxxxx'
        )




class Movie(models.Model):
    
    name = models.CharField(
        max_length=255,
        db_index=True
    )

    image = models.ImageField(
        upload_to='movies/'
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        db_index=True
    )
    
    trailer_url = models.URLField(
        max_length=500,
        blank=True,
        null=True
    )

    cast = models.TextField()

    description = models.TextField(
        blank=True,
        null=True
    )

    # MANY TO MANY GENRES

    genres = models.ManyToManyField(
        Genre,
        related_name='movies'
    )

    # LANGUAGE

    language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        related_name='movies',
        db_index=True,
        null=True,
        blank=True
    )

    # CREATED TIME

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    
    def get_youtube_embed_url(self):
        if not self.trailer_url:
            return None
        
        import re
        # Extract video ID from any valid YouTube URL format
        pattern = re.compile(
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
        )
        match = pattern.search(self.trailer_url)
        
        if match:
            video_id = match.group(1)
            # Return embed URL with security and performance params
            return (
                f'https://www.youtube-nocookie.com/embed/{video_id}'
                f'?rel=0&modestbranding=1'
            )
        return None
    
    
    
    
    class Meta:

        # DEFAULT ORDERING

        ordering = ['-created_at']

        # DATABASE INDEXES

        indexes = [

            # FAST RATING SORTING
            models.Index(fields=['rating']),

            # FAST DATE SORTING
            models.Index(fields=['created_at']),

            # FAST NAME SEARCH
            models.Index(fields=['name']),

            # FAST LANGUAGE FILTERING
            models.Index(fields=['language']),
        ]

    def __str__(self):

        return self.name


class Theater(models.Model):

    name = models.CharField(
        max_length=255
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='theaters'
    )

    time = models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'


class Seat(models.Model):

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='seats'
    )

    seat_number = models.CharField(
        max_length=10
    )

    is_booked = models.BooleanField(
        default=False
    )
    
    reserved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reserved_seats'
    )

    reserved_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=['is_booked']),
            models.Index(fields=['reserved_at']),  # fast expiry queries
        ]

    @property
    def is_reserved(self):
        if self.reserved_by and self.reserved_at:
            from django.utils import timezone
            # Reservation expires after 2 minutes
            return timezone.now() < self.reserved_at + timezone.timedelta(minutes=2)
        return False
    
    
    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'


class Booking(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE
    )

    booked_at = models.DateTimeField(
        auto_now_add=True
    )
    
    
    class Meta:
        indexes = [
            models.Index(fields=['booked_at']),   # fast date filtering
            models.Index(fields=['movie']),        # fast movie aggregation
            models.Index(fields=['theater']),      # fast theater aggregation
            models.Index(fields=['user']),         # fast user lookups
        ]

    def __str__(self):
        return f'Booking by {self.user.username} for {self.seat.seat_number} at {self.theater.name}'
    
    
    @receiver(post_save, sender=Seat)
    def sync_booking_on_seat_save(sender, instance, **kwargs):
        if not instance.is_booked:
            # When is_booked is unchecked in admin, delete the booking row too
            Booking.objects.filter(seat=instance).delete()
            
            
class Payment(models.Model):
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE
    )

    # Razorpay order ID — created server side
    razorpay_order_id = models.CharField(
        max_length=100,
        unique=True
    )

    # Razorpay payment ID — received after payment
    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    # Idempotency key — prevents duplicate transactions
    idempotency_key = models.CharField(
        max_length=100,
        unique=True
    )

    amount = models.IntegerField()  # in paise (100 paise = 1 rupee)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    seats = models.ManyToManyField(Seat)

    created_at = models.DateTimeField(auto_now_add=True)
    
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),      # fast status filtering
            models.Index(fields=['created_at']),  # fast date aggregation
        ]

    def __str__(self):
        return f'Payment {self.razorpay_order_id} by {self.user.username}'