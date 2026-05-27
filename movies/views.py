from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)

from django.contrib.auth.decorators import login_required

from django.db import IntegrityError, transaction

from django.core.paginator import Paginator

from django.db.models import Count, Q

from django.conf import settings

from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse, HttpResponseBadRequest

from .tasks import send_booking_email

from .models import (
    Movie,
    Theater,
    Seat,
    Booking,
    Genre,
    Language,
    Payment
)

import razorpay
import hmac
import hashlib
import uuid
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, ExtractHour
import datetime

from django.contrib.auth.models import User


logger = logging.getLogger(__name__)

razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


def movie_list(request):

    movies = Movie.objects.select_related(
        'language'
    ).prefetch_related(
        'genres'
    ).all()

    search_query = request.GET.get('search')

    if search_query:
        movies = movies.filter(name__icontains=search_query)

    genre_ids = request.GET.getlist('genre')
    genre_ids = [genre for genre in genre_ids if genre.isdigit()]

    if genre_ids:
        movies = movies.filter(genres__id__in=genre_ids).distinct()

    language_ids = request.GET.getlist('language')
    language_ids = [language for language in language_ids if language.isdigit()]

    if language_ids:
        movies = movies.filter(language__id__in=language_ids)

    sort = request.GET.get('sort')

    if sort == 'rating':
        movies = movies.order_by('-rating')
    elif sort == 'latest':
        movies = movies.order_by('-created_at')
    elif sort == 'oldest':
        movies = movies.order_by('created_at')
    else:
        movies = movies.order_by('-created_at')

    paginator = Paginator(movies, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    genres = Genre.objects.annotate(
        movie_count=Count(
            'movies',
            filter=Q(
                movies__language__id__in=language_ids
            ) if language_ids else Q()
        )
    )

    languages = Language.objects.annotate(
        movie_count=Count(
            'movies',
            filter=Q(
                movies__genres__id__in=genre_ids
            ) if genre_ids else Q()
        )
    )

    return render(
        request,
        'movies/movie_list.html',
        {
            'page_obj': page_obj,
            'genres': genres,
            'languages': languages,
        }
    )


def theater_list(request, movie_id):

    movie = get_object_or_404(Movie, id=movie_id)

    theaters = Theater.objects.filter(movie=movie)

    return render(
        request,
        'movies/theater_list.html',
        {
            'movie': movie,
            'theaters': theaters
        }
    )


def movie_detail(request, movie_id):

    movie = get_object_or_404(
        Movie.objects.select_related('language').prefetch_related('genres'),
        id=movie_id
    )

    return render(request, 'movies/movie_detail.html', {
        'movie': movie,
        'embed_url': movie.get_youtube_embed_url()
    })


@login_required(login_url='/login/')
def book_seats(request, theater_id):

    theater = get_object_or_404(Theater, id=theater_id)

    with transaction.atomic():
        if not Seat.objects.filter(theater=theater).exists():
            rows = ['A', 'B', 'C', 'D', 'E']
            seats_per_row = 10
            Seat.objects.bulk_create([
                Seat(theater=theater, seat_number=f"{row}{num}", is_booked=False)
                for row in rows
                for num in range(1, seats_per_row + 1)
            ])

    if request.method == 'POST':
        selected_seat_ids = request.POST.getlist('seats')

        if not selected_seat_ids:
            seats = Seat.objects.filter(theater=theater)
            return render(request, 'movies/seat_selection.html', {
                'theater': theater,
                'seats': seats,
                'error': 'No seat selected'
            })

        selected_seats = []
        error_seats = []

        # Reserve each seat atomically — prevents race conditions
        for seat_id in selected_seat_ids:
            with transaction.atomic():
                try:
                    # select_for_update locks the row so no other
                    # request can read/write it simultaneously
                    seat = Seat.objects.select_for_update().get(
                        id=int(seat_id),
                        theater=theater
                    )
                except Seat.DoesNotExist:
                    continue

                # Check if booked
                if seat.is_booked or Booking.objects.filter(seat=seat).exists():
                    error_seats.append(seat.seat_number)
                    continue

                # Check if reserved by someone else
                if seat.is_reserved and seat.reserved_by != request.user:
                    error_seats.append(seat.seat_number)
                    continue

                # Reserve the seat for this user for 2 minutes
                seat.reserved_by = request.user
                seat.reserved_at = timezone.now()
                seat.save()
                selected_seats.append(seat)

        if error_seats:
            seats = Seat.objects.filter(theater=theater)
            return render(request, 'movies/seat_selection.html', {
                'theater': theater,
                'seats': seats,
                'error': f'Seats {", ".join(error_seats)} are already reserved or booked'
            })

        if not selected_seats:
            seats = Seat.objects.filter(theater=theater)
            return render(request, 'movies/seat_selection.html', {
                'theater': theater,
                'seats': seats,
                'error': 'No valid seats selected'
            })

        amount = len(selected_seats) * 15000

        seat_ids_str = '-'.join(sorted([str(s.id) for s in selected_seats]))
        checkout_session_token = uuid.uuid4().hex[:6].upper()
        idempotency_key = f"{request.user.id}-{theater.id}-{seat_ids_str}-{checkout_session_token}"

        existing_payment = Payment.objects.filter(
            idempotency_key=idempotency_key,
            status='success'
        ).first()

        if existing_payment:
            seats = Seat.objects.filter(theater=theater)
            return render(request, 'movies/seat_selection.html', {
                'theater': theater,
                'seats': seats,
                'error': 'These seats are already booked by you'
            })

        try:
            razorpay_order = razorpay_client.order.create({
                'amount': amount,
                'currency': 'INR',
                'receipt': f'receipt_{uuid.uuid4().hex[:10]}',
                'payment_capture': 1
            })
        except Exception as e:
            logger.error(f'Razorpay order creation failed: {str(e)}')
            # Release reservations if order creation fails
            Seat.objects.filter(
                id__in=[s.id for s in selected_seats]
            ).update(reserved_by=None, reserved_at=None)
            seats = Seat.objects.filter(theater=theater)
            return render(request, 'movies/seat_selection.html', {
                'theater': theater,
                'seats': seats,
                'error': 'Payment service unavailable. Please try again.'
            })

        payment = Payment.objects.create(
            user=request.user,
            theater=theater,
            razorpay_order_id=razorpay_order['id'],
            idempotency_key=idempotency_key,
            amount=amount,
            status='pending'
        )
        payment.seats.set(selected_seats)

        return render(request, 'movies/payment.html', {
            'theater': theater,
            'selected_seats': selected_seats,
            'amount': int(amount / 100),
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'user': request.user,
            'reservation_timeout': 120,  # 2 minutes in seconds for frontend timer
        })

    seats = Seat.objects.filter(theater=theater)
    return render(request, 'movies/seat_selection.html', {
        'theater': theater,
        'seats': seats
    })


@login_required(login_url='/login/')
def payment_success(request):

    if request.method != 'POST':
        return redirect('movie_list')

    # Handle cancellation
    if request.POST.get('cancelled'):
        order_id = request.POST.get('razorpay_order_id')
        try:
            payment = Payment.objects.get(
                razorpay_order_id=order_id,
                user=request.user
            )
            payment.status = 'cancelled'
            payment.save()
        except Payment.DoesNotExist:
            pass
        return redirect('movie_list')

    razorpay_order_id = request.POST.get('razorpay_order_id')
    razorpay_payment_id = request.POST.get('razorpay_payment_id')
    razorpay_signature = request.POST.get('razorpay_signature')

    # Server-side signature verification — fraud prevention
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })

    except razorpay.errors.SignatureVerificationError:
        logger.error(
            f'Signature verification failed for order {razorpay_order_id}. '
            f'Possible fraud by user {request.user.id}'
        )
        return render(request, 'movies/payment_failed.html', {
            'error': 'Payment verification failed. Please contact support.'
        })

    # Confirm booking inside atomic block
    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(
                razorpay_order_id=razorpay_order_id,
                user=request.user
            )

            # Idempotency — skip if already processed
            if payment.status == 'success':
                return redirect('movie_list')

            payment.razorpay_payment_id = razorpay_payment_id
            payment.status = 'success'
            payment.save()

            booked_seat_numbers = []

            for seat in payment.seats.all():
                if not seat.is_booked:
                    Booking.objects.create(
                        user=request.user,
                        seat=seat,
                        movie=payment.theater.movie,
                        theater=payment.theater
                    )
                    seat.is_booked = True
                    seat.reserved_by = None
                    seat.reserved_at = None
                    seat.save()
                    booked_seat_numbers.append(seat.seat_number)

            if booked_seat_numbers:
                send_booking_email.delay(
                    request.user.email,
                    request.user.username,
                    payment.theater.movie.name,
                    payment.theater.name,
                    str(payment.theater.time),
                    ', '.join(booked_seat_numbers),
                    razorpay_payment_id
                )

    except Payment.DoesNotExist:
        logger.error(f'Payment not found for order {razorpay_order_id}')
        return render(request, 'movies/payment_failed.html', {
            'error': 'Payment record not found.'
        })

    return redirect('movie_list')


@csrf_exempt
def razorpay_webhook(request):

    if request.method != 'POST':
        return HttpResponseBadRequest()

    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    webhook_signature = request.headers.get('X-Razorpay-Signature', '')
    payload = request.body

    expected_signature = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, webhook_signature):
        logger.error('Invalid webhook signature — possible replay attack')
        return HttpResponseBadRequest('Invalid signature')

    import json
    data = json.loads(payload)
    event = data.get('event')

    if event == 'payment.captured':
        order_id = data['payload']['payment']['entity']['order_id']
        payment_id = data['payload']['payment']['entity']['id']

        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(
                    razorpay_order_id=order_id
                )

                if payment.status == 'success':
                    return JsonResponse({'status': 'already processed'})

                payment.razorpay_payment_id = payment_id
                payment.status = 'success'
                payment.save()

                for seat in payment.seats.all():
                    if not seat.is_booked:
                        Booking.objects.create(
                            user=payment.user,
                            seat=seat,
                            movie=payment.theater.movie,
                            theater=payment.theater
                        )
                        seat.is_booked = True
                        seat.save()

        except Payment.DoesNotExist:
            logger.error(f'Webhook: payment not found for order {order_id}')

    elif event == 'payment.failed':
        order_id = data['payload']['payment']['entity']['order_id']
        try:
            payment = Payment.objects.get(razorpay_order_id=order_id)
            payment.status = 'failed'
            payment.save()
            # Release reservations on payment failure
            payment.seats.update(reserved_by=None, reserved_at=None)
        except Payment.DoesNotExist:
            pass
    return JsonResponse({'status': 'ok'})



@staff_member_required(login_url='/login/')
def admin_dashboard(request):

    now = timezone.now()
    today = now.date()
    week_ago = now - datetime.timedelta(days=7)
    month_ago = now - datetime.timedelta(days=30)

    # ---- REVENUE ANALYTICS ----
    # All done at DB level — no data loaded into memory

    # Try cache first
    dashboard_data = cache.get('admin_dashboard_data')

    if not dashboard_data:

        # Daily revenue — sum of successful payments today
        daily_revenue = Payment.objects.filter(
            status='success',
            created_at__date=today
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        # Weekly revenue
        weekly_revenue = Payment.objects.filter(
            status='success',
            created_at__gte=week_ago
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        # Monthly revenue
        monthly_revenue = Payment.objects.filter(
            status='success',
            created_at__gte=month_ago
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

        # Daily revenue chart data — last 30 days grouped by day
        # TruncDay groups at DB level — never loads all rows into memory
        daily_revenue_chart = list(
            Payment.objects.filter(
                status='success',
                created_at__gte=month_ago
            ).annotate(
                day=TruncDay('created_at')
            ).values('day').annotate(
                total=Sum('amount')
            ).order_by('day')
        )

        # ---- MOST POPULAR MOVIES ----
        popular_movies = list(
            Booking.objects.values(
                'movie__name'
            ).annotate(
                booking_count=Count('id')
            ).order_by('-booking_count')[:10]
        )

        # ---- BUSIEST THEATERS ----
        # Occupancy rate = booked seats / total seats * 100
        busiest_theaters = list(
            Seat.objects.values(
                'theater__name',
                'theater__movie__name'
            ).annotate(
                total_seats=Count('id'),
                booked_seats=Count('id', filter=Q(is_booked=True)),
            ).annotate(
                occupancy_rate=Count(
                    'id', filter=Q(is_booked=True)
                ) * 100 / Count('id')
            ).order_by('-occupancy_rate')[:10]
        )

        # ---- PEAK BOOKING HOURS ----
        # ExtractHour groups by hour at DB level
        peak_hours = list(
            Booking.objects.annotate(
                hour=ExtractHour('booked_at')
            ).values('hour').annotate(
                booking_count=Count('id')
            ).order_by('-booking_count')[:24]
        )

        # ---- CANCELLATION RATE ----
        total_payments = Payment.objects.count()
        cancelled_payments = Payment.objects.filter(
            status='cancelled'
        ).count()
        failed_payments = Payment.objects.filter(
            status='failed'
        ).count()

        cancellation_rate = round(
            (cancelled_payments / total_payments * 100)
            if total_payments > 0 else 0, 2
        )

        failure_rate = round(
            (failed_payments / total_payments * 100)
            if total_payments > 0 else 0, 2
        )

        # ---- TOTAL BOOKINGS ----
        total_bookings = Booking.objects.count()
        total_users = User.objects.count()

        dashboard_data = {
            'daily_revenue': daily_revenue / 100,       # paise to rupees
            'weekly_revenue': weekly_revenue / 100,
            'monthly_revenue': monthly_revenue / 100,
            'daily_revenue_chart': daily_revenue_chart,
            'popular_movies': popular_movies,
            'busiest_theaters': busiest_theaters,
            'peak_hours': peak_hours,
            'cancellation_rate': cancellation_rate,
            'failure_rate': failure_rate,
            'total_bookings': total_bookings,
            'total_users': total_users,
            'cancelled_payments': cancelled_payments,
            'failed_payments': failed_payments,
        }

        # Cache for 5 minutes — prevents repeated heavy queries
        cache.set('admin_dashboard_data', dashboard_data, 300)

    return render(request, 'movies/admin_dashboard.html', dashboard_data)



@login_required(login_url='/login/')
def test_payment_success(request, order_id):
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(
                razorpay_order_id=order_id,
                user=request.user
            )
            if payment.status == 'success':
                return redirect('movie_list')

            payment.status = 'success'
            payment.razorpay_payment_id = f'test_pay_{uuid.uuid4().hex[:10]}'
            payment.save()

            booked_seat_numbers = []
            for seat in payment.seats.all():
                if not seat.is_booked:
                    Booking.objects.create(
                        user=request.user,
                        seat=seat,
                        movie=payment.theater.movie,
                        theater=payment.theater
                    )
                    seat.is_booked = True
                    seat.reserved_by = None
                    seat.reserved_at = None
                    seat.save()
                    booked_seat_numbers.append(seat.seat_number)

            if booked_seat_numbers:
                send_booking_email.delay(
                    request.user.email,
                    request.user.username,
                    payment.theater.movie.name,
                    payment.theater.name,
                    str(payment.theater.time),
                    ', '.join(booked_seat_numbers),
                    payment.razorpay_payment_id
                )
        except Payment.DoesNotExist:
            return redirect('movie_list')

    return redirect('movie_list')