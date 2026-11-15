# Blog API — Homework 3

Django blog with email authentication, JWT, Unfold admin, demo data and 50 ORM exercises.
Python 3.12 recommended. HW1/HW2 functionality is retained. No new dependencies for HW3.

## Local setup (Windows CMD)

Run from the directory containing `manage.py`:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements/dev.txt
python setup_local.py
python manage.py migrate
python manage.py seed
python manage.py queries
```

`setup_local.py` creates `settings/.env` with a random secret if absent; existing settings
are preserved. SQLite is the default local database. `seed --clear` replaces demo data
and preserves superusers; use it when you want fresh data with the HW3 date distribution.
Without `--clear`, another run adds data and leaves existing timestamps intact.

## Queries

```bat
python manage.py queries
python manage.py queries --number 31
python manage.py queries --number 6 --sql
python manage.py queries --number 41
```

Default execution runs 45 read exercises, skipping 40–44. Mutating exercises require an
explicit `--number`. #41 publishes drafts older than the sample cutoff, so counts change
until data is regenerated. #43 merges two sample categories and deletes the source.

Example output (counts and generated names vary):

```text
#31 categories_with_post_count — 1 SQL query
  Python {'post_count': 16}
  Databases {'post_count': 13}
  (8 rows)
```

The command previews at most five rows and reports the full result count. Annotation
values appear alongside model names. `--sql` prints SQL actually executed, including
statements issued while lazy querysets and related objects are evaluated.

Sample arguments are defined in `SAMPLE_ARGUMENTS` next to the management command.
`sample_arguments()` fills slugs, emails, title fragments and dates from current data.
This input discovery happens **before** measurement; the displayed SQL count measures
the exercise itself and result formatting. Empty results are legitimate (especially #26).
A full real run is in `docs/queries-example.txt`.

## Implementation

- `apps/blog/queries.py`: all 50 named functions and the `QUERIES` registry.
- `apps/blog/management/commands/queries.py`: runner, samples, previews and SQL capture.
- `apps/blog/management/commands/seed.py`: bulk insertion, then bulk timestamp updates.
- `apps/blog/constants.py`: generation rules, limits, display labels and thresholds.
- `apps/blog/test_hw3.py`: SQL budgets, edge cases, mutations, command and seed tests.

Seed posts span the last 365 days. Exactly round(30% × new post count) receive an update
1–30 days after creation, capped by now. Other timestamps are exactly equal. Comments
are dated between their parent post and now and belong only to published posts.
New post objects are reused for comment dates without reloading them after insertion.

Read exercises 1–39 and 48–50 execute one SQL statement, including empty results.
#45 uses `select_related` (one SQL); #46–47 use prefetch (at most two).
#41 performs one UPDATE and explicitly updates `updated_at`. #42 adds relations in bulk.
#43 is transactional. All filtering, grouping and ordering happens in the ORM/database.

## Verification

```bat
python manage.py test
ruff check .
python manage.py makemigrations --check --dry-run
python manage.py queries --number 24
python manage.py queries --number 26
```

After a fresh default seed, #24 returns 30 of 100 posts, and #26 returns zero comments.
There are 30 tests including the existing HW1/HW2 tests; SQL-budget tests exercise every
read function with populated and empty databases. No model schema changes in HW3.

## Optional admin and API

```bat
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/admin/. JWT endpoints: `/api/auth/token/` and
`/api/auth/token/refresh/`. The custom user signs in with email. Seed user password is
`BlogDemo-2026!` for local demonstrations. Use your own superuser for the admin.
Existing ERD and screenshots are in `docs/`.

## Git submission

Begin from `main` with HW2 already merged. Create `hw3`, copy the project files into the
repository, test, commit, merge `hw3` into `main` and push both branches. Keep `hw3`.
Detailed Windows commands are in `START_RU.txt`. Do not commit `.env`, `.venv`, the SQLite
database or caches. Submit the repository link through the course's required submission
form; uploading to GitHub alone does not submit the homework.
