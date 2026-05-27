from django.contrib import admin

from .models import (
    Movie,
    Theater,
    Seat,
    Booking,
    Genre,
    Language
)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):

    list_display = ['id', 'name']

    search_fields = ['name']


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):

    list_display = ['id', 'name']

    search_fields = ['name']


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):

    list_display = [
        'name',
        'rating',
        'language',
        'created_at'
    ]

    search_fields = [
        'name',
        'cast'
    ]

    list_filter = [
        'language',
        'genres',
        'rating'
    ]

    filter_horizontal = [
        'genres'
    ]


@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):

    list_display = [
        'name',
        'movie',
        'time'
    ]

    search_fields = [
        'name',
        'movie__name'
    ]


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):

    list_display = [
        'theater',
        'seat_number',
        'is_booked'
    ]

    list_filter = [
        'is_booked'
    ]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display = [
        'user',
        'seat',
        'movie',
        'theater',
        'booked_at'
    ]

    search_fields = [
        'user__username',
        'movie__name'
    ]