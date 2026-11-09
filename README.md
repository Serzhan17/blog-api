# Blog API — Homework 1

Editable Django project for Practice Work #1. Python 3.12+ recommended.

## Scope

Includes the required project layout, five models, email-based custom user and manager,
initial migrations, environment configuration, and ERD. Basic Django admin and JWT token
endpoints are included so authentication and models can be used immediately.
The supplied HW1 file does not define blog CRUD endpoint requirements: these are not
implemented here. HW2 seed and Unfold features are intentionally left for the next work.
No GitHub repository has been published and no Oqulabs submission has been made.

## Entity relationship diagram

![Blog ERD](docs/erd.svg)

The diagram was created before the model implementation. Django automatically creates
Post_tags for the many-to-many relationship. PermissionsMixin also provides Django's
standard groups, permissions and is_superuser fields. date_joined is an extra user field
for the admin dates section.

## Windows: start from CMD

Extract the archive, open the hw1 folder in VS Code, and select a Command Prompt terminal.
Run from the folder containing manage.py:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements/dev.txt
copy settings\.env.example settings\.env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the generated value into BLOG_SECRET_KEY in settings/.env, enclosed in double
quotes. Keep BLOG_ENV_ID=local. If Python 3.12 is not installed, use `py -m venv .venv`
with an installed supported Python version.

```bat
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/admin/ and log in with your email and password.
Password characters are not displayed while createsuperuser asks for the password.
The root URL `/` has no page; use `/admin/`.
Create a category and tags first, then a post and a comment.

## Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/dev.txt
cp settings/.env.example settings/.env
# Set BLOG_SECRET_KEY to a generated random value before continuing.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Editing map

| File | Purpose |
| --- | --- |
| apps/auths/models.py | User and email-based manager |
| apps/auths/forms.py | Admin user creation and editing |
| apps/auths/admin.py | User admin layout |
| apps/auths/urls.py | JWT routes |
| apps/blog/models.py | Category, Tag, Post and Comment |
| apps/blog/admin.py | Basic admin for blog models |
| settings/conf.py | BLOG_ environment variables |
| settings/base.py | Shared configuration |
| settings/env/local.py | SQLite and DEBUG=True |
| settings/env/prod.py | PostgreSQL and DEBUG=False |

After changing model fields:

```bash
python manage.py makemigrations
python manage.py migrate
```

Slug fields are unique and are entered explicitly in code. The admin prepopulates them
from names/titles; change a duplicate slug manually. User creation through the manager
requires first_name and last_name and lowercases the entire email address.

## JWT authentication

POST `/api/auth/token/` with JSON:

```json
{"email": "your-email@example.com", "password": "your-password"}
```

The response contains `access` and `refresh`. POST `/api/auth/token/refresh/` with
`{"refresh": "YOUR_REFRESH_TOKEN"}` for a new access token. Use
`Authorization: Bearer YOUR_ACCESS_TOKEN` for future protected API endpoints.
Create users through the admin or manager; public registration is not included.

## Verification

```bash
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
ruff check .
ruff format --check .
```

Tests cover password hashing, email normalization, required manager fields,
superuser flags, admin user creation, JWT login/refresh, inactive-user rejection,
admin pages, unique slugs and relationship deletion rules.

## Production configuration

Install `requirements/prod.txt`, set BLOG_ENV_ID=prod and configure all database
variables and BLOG_ALLOWED_HOSTS in settings/.env or the process environment.
Use a strong secret, an HTTPS reverse proxy, PostgreSQL and a production WSGI/ASGI
server configured by your hosting provider. Run migrations and collectstatic there.
Production is configured but has not been connected to a real PostgreSQL server here.

All project-specific environment variables use the BLOG_ prefix. manage.py reads the
environment selector through settings/bootstrap.py; WSGI and ASGI use the same helper.
Local settings then import base.py, which imports conf.py and reads settings/.env.
The .env, databases, logs and virtual environments are excluded from Git and this archive.
The logs directory is created automatically on startup.

## Git and submission

On GitHub, create a PUBLIC repository called `blog-api` without initial files.
Inside the extracted hw1 folder run (replace YOUR_USERNAME):

```bash
git init -b main
git commit --allow-empty -m "Initialize repository"
git switch -c hw1
git add .
git commit -m "Implement Homework 1 blog models and configuration"
git switch main
git merge --no-ff hw1 -m "Merge Homework 1"
git remote add origin https://github.com/YOUR_USERNAME/blog-api.git
git push -u origin main
git push -u origin hw1
```

Keep branch hw1. For the second assignment create hw2 from main.
Folder name hw1 and Git branch hw1 are different things.
Follow the instructor's Oqulabs submission instructions once available.

## References

- https://docs.djangoproject.com/en/5.2/topics/auth/customizing/
- https://www.django-rest-framework.org/api-guide/authentication/
- https://django-rest-framework-simplejwt.readthedocs.io/en/stable/
