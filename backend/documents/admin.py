from django.contrib import admin

from documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """본문을 고쳐도 청크와 Chroma는 그대로다. 검색에 반영하려면 다시 빌드한다."""

    list_display = ('title', 'doc_type', 'lang', 'topic', 'needs_review', 'updated_at')
    list_filter = ('doc_type', 'lang', 'needs_review')
    list_select_related = ('artwork',)
    search_fields = ('title', 'doc_key')
    autocomplete_fields = ('artwork',)
