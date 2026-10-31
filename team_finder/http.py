from functools import wraps

from django.http import JsonResponse


def json_post(view):
    """Session authentication and method errors in the format expected by fetch."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method != "POST":
            response = JsonResponse({"error": "Разрешён только POST."}, status=405)
            response["Allow"] = "POST"
            return response
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Войдите в аккаунт."}, status=403)
        return view(request, *args, **kwargs)

    return wrapped
