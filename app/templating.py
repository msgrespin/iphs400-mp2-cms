"""The shared Jinja environment."""
from fastapi.templating import Jinja2Templates

from app import content, settings

templates = Jinja2Templates(directory=str(settings.TEMPLATES))
templates.env.globals["eastern"] = content.eastern
