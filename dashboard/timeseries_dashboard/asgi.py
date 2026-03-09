"""
ASGI config for timeseries_dashboard project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from project_config import configure_mlflow

configure_mlflow()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timeseries_dashboard.settings')

application = get_asgi_application()
