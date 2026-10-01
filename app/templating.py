"""The shared Jinja environment."""
from fastapi.templating import Jinja2Templates

from app import settings

templates = Jinja2Templates(directory=str(settings.TEMPLATES))
