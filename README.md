# Social Media API

RESTful API for a social media platform built with Django, Django REST Framework, Celery, Redis, and Docker.

## Features

- **Authentication:** Custom User model with email login, registration, token authentication, and token invalidation on logout.
- **User Profiles & Search:** View, update, and delete own profile (including avatar upload); view other users' profiles and search by username, email, or name.
- **Follow System:** Follow and unfollow users, view followers and following lists.
- **Posts & Feed:** Create posts with text and optional images, retrieve feed (own posts + followed users' posts), filter by `#hashtags` or author.
- **Likes & Comments:** Like/unlike posts, view liked posts, add/edit/delete comments.
- **Scheduled Posts:** Schedule future post publication using Celery and Redis.
- **Permissions:** Role-based access control ensuring users can only edit/delete their own profiles, posts, and comments.
- **API Documentation:** Interactive Swagger UI and ReDoc powered by `drf-spectacular`.

## Tech Stack

- Python 3.12, Django, Django REST Framework
- Celery & Redis
- Docker & Docker Compose
- OpenAPI 3 (`drf-spectacular`)

## Quick Start (Docker)

1. Clone the repository:
   ```bash
   git clone https://github.com/agridenko/social_media_api
   cd social_media_api
   ```

2. Build and run containers:
   ```bash
   docker compose up --build
   ```

3. Access the API and documentation:
   - **Swagger UI:** `http://127.0.0.1:8000/api/docs/swagger/`
   - **Admin Panel:** `http://127.0.0.1:8000/admin/`

## Running Tests & Coverage
```bash
   coverage run --source='user,social' manage.py test
   coverage report -m
   ```