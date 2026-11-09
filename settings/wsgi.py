from django.core.wsgi import get_wsgi_application

from settings.bootstrap import configure_settings

configure_settings()
application = get_wsgi_application()
