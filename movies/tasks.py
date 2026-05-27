
    
    
import logging

from celery import shared_task

from django.core.mail import EmailMultiAlternatives

from django.template.loader import render_to_string

from django.conf import settings

from celery.schedules import crontab


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3
)
def send_booking_email(
    self,
    user_email,
    username,
    movie_name,
    theater_name,
    theater_time,
    seats,
    payment_id
):

    try:

        html_content = render_to_string(
            'movies/emails/booking_confirmation.html',
            {
                'user': {
                    'username': username
                },

                'movie': {
                    'name': movie_name
                },

                'theater': {
                    'name': theater_name,
                    'time': theater_time
                },

                'seats': seats,

                'payment_id': payment_id
            }
        )

        email = EmailMultiAlternatives(

            subject='Booking Confirmation',

            body='Booking Confirmed',

            from_email=settings.DEFAULT_FROM_EMAIL,

            to=[user_email]
        )

        email.attach_alternative(
            html_content,
            "text/html"
        )

        email.send()

        logger.info(
            f"Booking email sent to {user_email}"
        )

    except Exception as exc:

        logger.error(
            f"Email failed: {str(exc)}"
        )

        raise self.retry(
            exc=exc,
            countdown=10
        )
        
        
        
@shared_task
def release_expired_reservations():
    """
    Runs every minute via Celery Beat.
    Releases any seat reservations older than 2 minutes.
    Never loads all seats into memory — uses DB-level update.
    """
    from django.utils import timezone
    from .models import Seat

    expiry_time = timezone.now() - timezone.timedelta(minutes=2)

    # DB-level bulk update — no Python loop, no memory issues
    expired_count = Seat.objects.filter(
        is_booked=False,
        reserved_by__isnull=False,
        reserved_at__lt=expiry_time
    ).update(
        reserved_by=None,
        reserved_at=None
    )

    logger.info(f'Released {expired_count} expired seat reservations')
    return expired_count