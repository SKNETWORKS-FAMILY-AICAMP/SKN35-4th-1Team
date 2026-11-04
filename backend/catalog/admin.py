from django.contrib import admin

from catalog.models import Artist, ArtMovement, Artwork


@admin.register(ArtMovement)
class ArtMovementAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_en', 'slug')
    search_fields = ('name', 'name_en', 'slug')


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_en', 'movement', 'birth_year', 'death_year')
    list_filter = ('movement',)
    list_select_related = ('movement',)
    search_fields = ('name', 'name_en', 'slug')


@admin.register(Artwork)
class ArtworkAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist', 'movement', 'year_label', 'is_featured')
    list_filter = ('is_featured', 'movement', 'artist')
    list_select_related = ('artist', 'movement')
    search_fields = ('title', 'title_en', 'slug')
    autocomplete_fields = ('artist', 'movement')
