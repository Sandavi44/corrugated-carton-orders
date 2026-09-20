import os


def demo_mode(request):
    """Expose DEMO_MODE to all templates so the login page can show the Try Demo button."""
    return {"DEMO_MODE": os.environ.get("DEMO_MODE", "").lower() == "true"}
