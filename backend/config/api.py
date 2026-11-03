from ninja import NinjaAPI

api = NinjaAPI(title="Docentalk API")


@api.get("/health")
def health(request):
    return {"status": "ok"}
