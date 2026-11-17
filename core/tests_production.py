import os
from pathlib import Path
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core import production_settings


class ProductionSettingsAndSecuritySanityTests(TestCase):
    """
    Validates production settings configuration, security hardening headers,
    and deployment artifact integrity.
    """

    def test_production_settings_debug_is_strictly_false(self):
        self.assertFalse(production_settings.DEBUG)

    def test_production_ssl_and_cookie_security(self):
        self.assertTrue(production_settings.SESSION_COOKIE_SECURE)
        self.assertTrue(production_settings.CSRF_COOKIE_SECURE)
        self.assertTrue(production_settings.SECURE_BROWSER_XSS_FILTER)
        self.assertTrue(production_settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(production_settings.X_FRAME_OPTIONS, 'DENY')
        self.assertEqual(production_settings.SECURE_HSTS_SECONDS, 31536000)
        self.assertTrue(production_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(production_settings.SECURE_HSTS_PRELOAD)

    def test_production_allowed_hosts_and_cors(self):
        self.assertIn('sonyfeedingkurtis.com', production_settings.ALLOWED_HOSTS)
        self.assertIn('www.sonyfeedingkurtis.com', production_settings.ALLOWED_HOSTS)
        self.assertIn('https://sonyfeedingkurtis.com', production_settings.CORS_ALLOWED_ORIGINS)
        self.assertTrue(production_settings.CORS_ALLOW_CREDENTIALS)

    def test_deployment_artifacts_exist_and_non_empty(self):
        base_dir = Path(settings.BASE_DIR)
        deploy_dir = base_dir / 'deploy'

        nginx_conf = deploy_dir / 'nginx.conf'
        gunicorn_service = deploy_dir / 'gunicorn.service'
        gunicorn_conf = deploy_dir / 'gunicorn_conf.py'
        deploy_sh = deploy_dir / 'deploy.sh'
        setup_sh = deploy_dir / 'setup_vps.sh'

        for artifact in (nginx_conf, gunicorn_service, gunicorn_conf, deploy_sh, setup_sh):
            self.assertTrue(artifact.exists(), f"Missing deployment artifact: {artifact.name}")
            self.assertTrue(artifact.stat().st_size > 100, f"Artifact empty or too small: {artifact.name}")

        # Check Nginx config content
        nginx_content = nginx_conf.read_text(encoding='utf-8')
        self.assertIn('upstream sony_backend_upstream', nginx_content)
        self.assertIn('client_max_body_size 50M', nginx_content)
        self.assertIn('location /static/', nginx_content)
        self.assertIn('location /media/', nginx_content)
        self.assertIn('location ~ ^/(api|admin)/', nginx_content)

        # Check Gunicorn service content
        service_content = gunicorn_service.read_text(encoding='utf-8')
        self.assertIn('ExecStart', service_content)
        self.assertIn('core.wsgi:application', service_content)

    def test_health_check_endpoint(self):
        client = APIClient()
        response = client.get(reverse('health_check'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertEqual(response.data['service'], 'sony-feeding-kurtis-backend')
        self.assertEqual(response.data['version'], '1.0.0')
